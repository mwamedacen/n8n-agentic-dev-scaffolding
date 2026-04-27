#!/usr/bin/env python3
"""Insert lock acquire / release Execute Workflow nodes around a workflow's main flow."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from helpers.workspace import workspace_root


_LOCK_ACQUIRE_NODE_NAME = "Lock Acquire"
_LOCK_RELEASE_NODE_NAME = "Lock Release"
_DEFAULT_TTL_SECONDS = 86400  # 24h — bounded leak on crash


def _make_execute_workflow_node(
    name: str,
    target_workflow_placeholder: str,
    position: list,
    inputs: dict,
) -> dict:
    """Build an Execute Workflow node with `inputs` mapped into workflowInputs.value."""
    return {
        "id": "{{HYDRATE:uuid:" + name.lower().replace(" ", "-") + "}}",
        "name": name,
        "type": "n8n-nodes-base.executeWorkflow",
        "typeVersion": 1.2,
        "position": position,
        "parameters": {
            "source": "database",
            "workflowId": {
                "__rl": True,
                "value": target_workflow_placeholder,
                "mode": "id",
            },
            "workflowInputs": {
                "mappingMode": "defineBelow",
                "value": inputs,
                "matchingColumns": [],
                "schema": [],
            },
            "options": {},
        },
    }


def _insert_lock(
    template: dict,
    scope_expr: str,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    fail_fast: bool = False,
) -> dict:
    """Splice in two Execute Workflow nodes, one before the main flow, one after."""
    nodes = template.setdefault("nodes", [])
    connections = template.setdefault("connections", {})

    if any(n.get("name") == _LOCK_ACQUIRE_NODE_NAME for n in nodes):
        raise SystemExit(f"Workflow already has a '{_LOCK_ACQUIRE_NODE_NAME}' node; refusing to add again")

    # Find the trigger (a node with no inbound connection — i.e. nobody references it)
    referenced: set[str] = set()
    for src_name, by_type in connections.items():
        for type_branches in by_type.values():
            for branch in type_branches:
                for c in branch:
                    referenced.add(c.get("node"))
    triggers = [n for n in nodes if n.get("name") not in referenced]
    if not triggers:
        raise SystemExit("Could not detect a trigger node (no node lacks inbound connections)")
    trigger = triggers[0]
    trigger_name = trigger["name"]

    # Existing trigger's outbound connections
    trigger_out = connections.get(trigger_name, {}).get("main", [[]])
    first_branch = trigger_out[0] if trigger_out else []

    trigger_pos = trigger.get("position") or [240, 300]
    acquire_pos = [trigger_pos[0] + 220, trigger_pos[1]]

    # Push every other node 440 right (220 for acquire + 220 for spacing) so we have room
    for n in nodes:
        if n is trigger:
            continue
        pos = n.get("position") or [0, 0]
        n["position"] = [pos[0] + 440, pos[1]]

    # Acquire input contract — the lock_acquisition primitive expects six fields.
    # workflow_id / workflow_name / execution_id are passed as n8n expressions so the
    # primitive captures the CALLING workflow's identity (not the lock workflow's).
    acquire_inputs = {
        "scope": scope_expr,
        "workflow_id": "={{ $workflow.id }}",
        "workflow_name": "={{ $workflow.name }}",
        "wait_till_lock_released": not fail_fast,
        "execution_id": "={{ $execution.id }}",
        "ttl_seconds": ttl_seconds,
    }
    acquire = _make_execute_workflow_node(
        _LOCK_ACQUIRE_NODE_NAME,
        "{{HYDRATE:env:workflows.lock_acquisition.id}}",
        acquire_pos,
        acquire_inputs,
    )

    # Release input contract — capture the lock_id returned by the acquire node so the
    # release call presents a matching token (token-fencing safety model).
    release_pos = [trigger_pos[0] + 880, trigger_pos[1]]
    release_inputs = {
        "lock_id": "={{ $('" + _LOCK_ACQUIRE_NODE_NAME + "').item.json.lock_id }}",
        "scope": scope_expr,
    }
    release = _make_execute_workflow_node(
        _LOCK_RELEASE_NODE_NAME,
        "{{HYDRATE:env:workflows.lock_release.id}}",
        release_pos,
        release_inputs,
    )

    nodes.append(acquire)
    nodes.append(release)

    # Wire: trigger → acquire → (whatever was first) ... → release
    connections[trigger_name] = {"main": [[{"node": _LOCK_ACQUIRE_NODE_NAME, "type": "main", "index": 0}]]}
    connections[_LOCK_ACQUIRE_NODE_NAME] = {"main": [first_branch]} if first_branch else {"main": [[]]}

    # Find terminal node(s): nodes that have no outbound connection
    outbound_names = set(connections.keys())
    terminals = [n["name"] for n in nodes if n["name"] not in outbound_names and n["name"] not in (_LOCK_ACQUIRE_NODE_NAME, _LOCK_RELEASE_NODE_NAME, trigger_name)]
    if terminals:
        for t in terminals:
            connections[t] = {"main": [[{"node": _LOCK_RELEASE_NODE_NAME, "type": "main", "index": 0}]]}
    else:
        # No real downstream content — wire acquire directly to release
        connections[_LOCK_ACQUIRE_NODE_NAME] = {"main": [[{"node": _LOCK_RELEASE_NODE_NAME, "type": "main", "index": 0}]]}

    return template


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--workflow-key", required=True, dest="workflow_key")
    parser.add_argument("--lock-on-error", action="store_true", dest="lock_on_error")
    parser.add_argument("--scope-expression", default="={{ $execution.id }}", dest="scope_expression")
    parser.add_argument(
        "--ttl-seconds",
        type=int,
        default=_DEFAULT_TTL_SECONDS,
        dest="ttl_seconds",
        help="Lock TTL in seconds (default 86400 = 24h). Stale locks self-heal on next contention.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        dest="fail_fast",
        help="Pass wait_till_lock_released=false; fail immediately if lock is held instead of waiting.",
    )
    args = parser.parse_args()

    ws = workspace_root(args.workspace)

    # Sanity: lock primitives must already exist in the workspace
    for prim in ("lock_acquisition", "lock_release"):
        if not (ws / "n8n-workflows-template" / f"{prim}.template.json").exists():
            print(f"ERROR: primitive '{prim}' not found in workspace. Run create-lock first.", file=sys.stderr)
            sys.exit(1)

    template_path = ws / "n8n-workflows-template" / f"{args.workflow_key}.template.json"
    if not template_path.exists():
        print(f"ERROR: workflow template not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    template = json.loads(template_path.read_text())
    template = _insert_lock(
        template,
        args.scope_expression,
        ttl_seconds=args.ttl_seconds,
        fail_fast=args.fail_fast,
    )
    template_path.write_text(json.dumps(template, indent=2))
    print(f"  Inserted lock acquire/release in {template_path}")

    if args.lock_on_error:
        import subprocess
        cmd = [
            sys.executable,
            str(Path(__file__).parent / "register_error_handler.py"),
            "--workspace", str(ws),
            "--workflow-key", args.workflow_key,
            "--handler-key", "error_handler_lock_cleanup",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(r.stdout)
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            sys.exit(r.returncode)
    print("add-lock-to-workflow complete.")


if __name__ == "__main__":
    main()
