#!/usr/bin/env python3
"""meta-evals/runner/state.py — snapshot + diff n8n instance state for eval runs.

Two subcommands:

  snapshot — pull workflows, recent executions, and variables from the n8n
             instance and write a JSON snapshot. Used before + after each
             scenario to compute state-shaped grading signal.

  diff     — given two snapshots, emit a human-readable change log
             (workflows added/removed/changed-active-state, executions
             recorded since `before`, variables added/removed).

The snapshot is intentionally narrow: only the fields that signal "the agent
did something visible on the instance". We don't capture the full nodes array
on every workflow — too noisy to diff and not what we're grading.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Locate the harness root so we can import its helpers.
HARNESS_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HARNESS_ROOT))

from helpers.config import load_env, load_yaml  # noqa: E402
from helpers.n8n_client import N8nClient  # noqa: E402


def _client_for(env: str, workspace: Path) -> N8nClient:
    """Build an N8nClient against <workspace>/n8n-config/<env>.yml + .env.<env>."""
    import os
    load_env(env, workspace)
    data = load_yaml(env, workspace)
    instance = data.get("n8n", {}).get("instanceName", "")
    api_key = os.environ.get("N8N_API_KEY", "")
    return N8nClient(base_url=instance, api_key=api_key)


def snapshot(env: str, workspace: Path, recent_minutes: int = 5) -> dict:
    """Return a state snapshot suitable for diffing pre/post a scenario."""
    client = _client_for(env, workspace)

    workflows: list[dict] = []
    try:
        # GET /workflows paginates with cursor. For the eval, capture the first
        # 250 (n8n's default page cap). 250 is fine for the audit instance and
        # most user instances; document the cap in the snapshot itself.
        resp = client.get("workflows", params={"limit": 250})
        data = resp.get("data") if isinstance(resp, dict) else resp
        for wf in (data or []):
            workflows.append({
                "id": wf.get("id"),
                "name": wf.get("name"),
                "active": bool(wf.get("active")),
                "isArchived": bool(wf.get("isArchived")),
                "tags": [t.get("name") for t in (wf.get("tags") or [])],
            })
    except Exception as e:
        workflows = [{"_error": str(e)}]

    # Recent executions (last `recent_minutes` minutes) — establishes the
    # post-scenario baseline so the grader can detect "an execution was created".
    # n8n's GET /executions has no native time filter, so we pull the latest 250
    # and trust the orchestrator to pre-snapshot before and post-snapshot after,
    # taking the set difference on execution `id`.
    executions: list[dict] = []
    try:
        resp = client.get("executions", params={"limit": 250})
        data = resp.get("data") if isinstance(resp, dict) else resp
        for e in (data or []):
            executions.append({
                "id": str(e.get("id")),
                "status": e.get("status"),
                "mode": e.get("mode"),
                "workflowId": e.get("workflowId"),
                "startedAt": e.get("startedAt"),
                "finished": bool(e.get("finished")),
            })
    except Exception as e:
        executions = [{"_error": str(e)}]

    variables: list[dict] = []
    try:
        resp = client.get("variables")
        data = resp.get("data") if isinstance(resp, dict) else resp
        for v in (data or []):
            variables.append({
                "id": v.get("id"),
                "key": v.get("key"),
                "type": v.get("type"),
            })
    except Exception as e:
        variables = [{"_error": str(e)}]

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "env": env,
        "workspace": str(workspace),
        "workflow_cap": 250,
        "execution_cap": 250,
        "workflows": workflows,
        "executions": executions,
        "variables": variables,
    }


def diff(before: dict, after: dict) -> dict:
    """Compute set-difference between two snapshots. Returns a structured diff."""
    def _by_id(items, key="id"):
        return {str(it.get(key)): it for it in (items or []) if it.get(key) is not None}

    before_wf = _by_id(before.get("workflows") or [])
    after_wf = _by_id(after.get("workflows") or [])

    added_workflows = [after_wf[k] for k in after_wf.keys() - before_wf.keys()]
    removed_workflows = [before_wf[k] for k in before_wf.keys() - after_wf.keys()]
    state_changed_workflows = []
    for wid in before_wf.keys() & after_wf.keys():
        b, a = before_wf[wid], after_wf[wid]
        if (b.get("active"), b.get("isArchived")) != (a.get("active"), a.get("isArchived")):
            state_changed_workflows.append({
                "id": wid,
                "name": a.get("name"),
                "before": {"active": b.get("active"), "isArchived": b.get("isArchived")},
                "after": {"active": a.get("active"), "isArchived": a.get("isArchived")},
            })

    before_ex = _by_id(before.get("executions") or [])
    after_ex = _by_id(after.get("executions") or [])
    new_executions = [after_ex[k] for k in after_ex.keys() - before_ex.keys()]
    # Executions don't get removed in normal operation; we don't track that.

    before_var = _by_id(before.get("variables") or [])
    after_var = _by_id(after.get("variables") or [])
    added_variables = [after_var[k] for k in after_var.keys() - before_var.keys()]
    removed_variables = [before_var[k] for k in before_var.keys() - after_var.keys()]

    return {
        "before_captured_at": before.get("captured_at"),
        "after_captured_at": after.get("captured_at"),
        "added_workflows": added_workflows,
        "removed_workflows": removed_workflows,
        "state_changed_workflows": state_changed_workflows,
        "new_executions": new_executions,
        "added_variables": added_variables,
        "removed_variables": removed_variables,
        "summary": {
            "n_added_workflows": len(added_workflows),
            "n_removed_workflows": len(removed_workflows),
            "n_state_changed_workflows": len(state_changed_workflows),
            "n_new_executions": len(new_executions),
            "n_added_variables": len(added_variables),
            "n_removed_variables": len(removed_variables),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_snap = sub.add_parser("snapshot", help="Pull a state snapshot from the n8n instance.")
    p_snap.add_argument("--env", required=True)
    p_snap.add_argument("--workspace", required=True, type=Path,
                        help="Path to a workspace whose n8n-config/<env>.yml + .env.<env> we should read.")
    p_snap.add_argument("--output", required=True, type=Path,
                        help="Where to write the snapshot JSON.")

    p_diff = sub.add_parser("diff", help="Diff two snapshots, emit JSON change log.")
    p_diff.add_argument("--before", required=True, type=Path)
    p_diff.add_argument("--after", required=True, type=Path)
    p_diff.add_argument("--output", required=True, type=Path,
                        help="Where to write the diff JSON.")

    args = parser.parse_args()

    if args.cmd == "snapshot":
        snap = snapshot(args.env, args.workspace)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(snap, indent=2))
        print(f"Snapshot written to {args.output} "
              f"(workflows={len(snap['workflows'])}, "
              f"executions={len(snap['executions'])}, "
              f"variables={len(snap['variables'])})")
    elif args.cmd == "diff":
        before = json.loads(args.before.read_text())
        after = json.loads(args.after.read_text())
        d = diff(before, after)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(d, indent=2))
        s = d["summary"]
        print(f"Diff written to {args.output} "
              f"(+{s['n_added_workflows']}wf, "
              f"~{s['n_state_changed_workflows']}wf-state, "
              f"+{s['n_new_executions']}exec, "
              f"+{s['n_added_variables']}var, "
              f"-{s['n_removed_variables']}var)")
    else:
        parser.error(f"Unknown subcommand: {args.cmd}")


if __name__ == "__main__":
    main()
