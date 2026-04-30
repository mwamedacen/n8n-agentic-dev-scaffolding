#!/usr/bin/env python3
"""meta-evals/runner/cleanup.py — post-scenario cleanup of n8n + Redis state.

For each live-write eval scenario the sub-agent may have:
- created workflows on the n8n instance
- created variables
- left lock / rate-limit keys in Redis (these self-clean via TTL)

This script:
1. Lists all workflows on the instance whose name OR key contains the eval
   prefix (e.g. `evolI-eval-1777999999`). For each, deactivate + archive via
   direct n8n REST (the harness's `archive.py` requires the workflow to be
   registered in the workspace YAML — we don't depend on that here, since the
   sub-agent may have created workflows the YAML doesn't know about).
2. Lists variables whose `key` starts with the eval prefix and deletes them.
3. Does NOT touch Redis directly — keys auto-expire via the short TTLs that
   eval scenarios use (≤60 s in resilience scenarios). For longer-lived eval
   keys, document and accept the leakage; the next eval-prefix is unique so
   no collisions across runs.

Run via:

    python3 meta-evals/runner/cleanup.py cleanup \\
      --env dev --workspace <ws> --eval-prefix evolI-eval-<run-id>

Cleanup is **rule-based and rigid** — we don't trust the eval'd agent to
clean up after itself; the cleanup is part of the eval scaffolding, not
part of what's being graded.
"""
import argparse
import json
import os
import sys
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HARNESS_ROOT))

from helpers.config import load_env, load_yaml  # noqa: E402
from helpers.n8n_client import N8nClient  # noqa: E402


def _client(env: str, workspace: Path) -> N8nClient:
    load_env(env, workspace)
    data = load_yaml(env, workspace)
    return N8nClient(
        base_url=data.get("n8n", {}).get("instanceName", ""),
        api_key=os.environ.get("N8N_API_KEY", ""),
    )


def _matches_prefix(value: str, prefix: str) -> bool:
    if not value or not prefix:
        return False
    return prefix in value


def cleanup_workflows(client: N8nClient, eval_prefix: str) -> dict:
    """Find every workflow whose name contains eval_prefix; deactivate + archive each."""
    out = {"deactivated": [], "archived": [], "failed": []}
    try:
        resp = client.get("workflows", params={"limit": 250})
        rows = resp.get("data") if isinstance(resp, dict) else resp
    except Exception as e:
        out["_list_error"] = str(e)
        return out

    for wf in (rows or []):
        wf_id = wf.get("id")
        wf_name = wf.get("name") or ""
        if not _matches_prefix(wf_name, eval_prefix):
            continue
        # Deactivate first (no-op if already inactive); ignore failures.
        if wf.get("active"):
            try:
                client.post(f"workflows/{wf_id}/deactivate")
                out["deactivated"].append({"id": wf_id, "name": wf_name})
            except Exception as e:
                out["failed"].append({"id": wf_id, "name": wf_name, "step": "deactivate", "error": str(e)})
                # Still attempt archive below.
        # Archive (idempotent).
        if not wf.get("isArchived"):
            try:
                client.post(f"workflows/{wf_id}/archive")
                out["archived"].append({"id": wf_id, "name": wf_name})
            except Exception as e:
                out["failed"].append({"id": wf_id, "name": wf_name, "step": "archive", "error": str(e)})
    return out


def cleanup_variables(client: N8nClient, eval_prefix: str) -> dict:
    """Find every variable whose key contains eval_prefix; delete."""
    out = {"deleted": [], "failed": []}
    try:
        resp = client.get("variables")
        rows = resp.get("data") if isinstance(resp, dict) else resp
    except Exception as e:
        out["_list_error"] = str(e)
        return out

    for v in (rows or []):
        vid = v.get("id")
        vkey = v.get("key") or ""
        if not _matches_prefix(vkey, eval_prefix):
            continue
        try:
            client.delete(f"variables/{vid}")
            out["deleted"].append({"id": vid, "key": vkey})
        except Exception as e:
            out["failed"].append({"id": vid, "key": vkey, "error": str(e)})
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("cleanup", help="Run all cleanup steps for one scenario.")
    p.add_argument("--env", required=True)
    p.add_argument("--workspace", required=True, type=Path)
    p.add_argument("--eval-prefix", required=True,
                   help="Substring to match in workflow names + variable keys.")
    p.add_argument("--output", type=Path, default=None,
                   help="Optional JSON report path; default stdout only.")

    args = parser.parse_args()
    if args.cmd != "cleanup":
        parser.error(f"unknown subcommand {args.cmd}")

    client = _client(args.env, args.workspace)
    report = {
        "env": args.env,
        "eval_prefix": args.eval_prefix,
        "workflows": cleanup_workflows(client, args.eval_prefix),
        "variables": cleanup_variables(client, args.eval_prefix),
    }
    blob = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(blob)
    print(blob)
    wf = report["workflows"]
    var = report["variables"]
    print(
        f"\nCleanup complete: deactivated={len(wf.get('deactivated', []))}, "
        f"archived={len(wf.get('archived', []))}, "
        f"variables_deleted={len(var.get('deleted', []))}, "
        f"failed={len(wf.get('failed', [])) + len(var.get('failed', []))}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
