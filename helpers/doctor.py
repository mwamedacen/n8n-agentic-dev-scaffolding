#!/usr/bin/env python3
"""Health check for an n8n-harness workspace."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

from helpers.workspace import workspace_root

OK, WARN, FAIL = "ok", "warn", "fail"
_ICONS = {OK: "✓", WARN: "⚠", FAIL: "✗"}


def _row(state: str, label: str, detail: str = "") -> tuple:
    return (state, label, detail)


def _fmt(state: str, label: str, detail: str = "") -> str:
    suffix = f" — {detail}" if detail else ""
    return f"  [{_ICONS[state]}] {label}{suffix}"


def _check_workspace(ws: Path) -> list:
    required = [ws / "n8n-config", ws / "n8n-workflows-template"]
    missing = [str(d) for d in required if not d.is_dir()]
    if missing:
        return [_row(FAIL, "workspace tree", f"missing: {', '.join(missing)}")]
    return [_row(OK, "workspace tree", str(ws))]


def _check_env_yaml(ws: Path, env: str) -> list:
    rows = []
    yaml_file = ws / "n8n-config" / f"{env}.yml"
    if not yaml_file.exists():
        return [_row(FAIL, f"{env}.yml", "file not found")]
    try:
        with open(yaml_file) as f:
            data = yaml.safe_load(f) or {}
        rows.append(_row(OK, f"{env}.yml", "parses OK"))
    except Exception as e:
        return [_row(FAIL, f"{env}.yml", str(e))]

    workflows = data.get("workflows", {}) or {}
    placeholder_keys = [
        k for k, v in workflows.items()
        if isinstance(v, dict) and (
            not v.get("id")
            or str(v.get("id", "")).startswith("your-")
            or v.get("id") == "placeholder"
        )
    ]
    if placeholder_keys:
        rows.append(_row(WARN, f"{env} workflow IDs", f"placeholder IDs: {', '.join(placeholder_keys)}"))
    elif workflows:
        rows.append(_row(OK, f"{env} workflow IDs", f"{len(workflows)} configured"))
    else:
        rows.append(_row(WARN, f"{env} workflow IDs", "no workflows configured yet"))
    return rows


def _check_n8n_api(ws: Path, env: str) -> list:
    try:
        from helpers.config import load_yaml, load_env
        import os
        data = load_yaml(env, ws)
        load_env(env, ws)
        api_key = os.environ.get("N8N_API_KEY", "")
        if not api_key:
            return [_row(WARN, f"{env} API key", "N8N_API_KEY not set in .env")]
        from helpers.n8n_client import N8nClient
        instance = data.get("n8n", {}).get("instanceName", "")
        N8nClient(base_url=instance, api_key=api_key).get("workflows", params={"limit": 1})
        return [_row(OK, f"{env} n8n API", "reachable")]
    except Exception as e:
        return [_row(FAIL, f"{env} n8n API", str(e))]


def _check_templates(ws: Path) -> list:
    template_dir = ws / "n8n-workflows-template"
    templates = list(template_dir.glob("*.template.json")) if template_dir.is_dir() else []
    if not templates:
        return [_row(WARN, "workflow templates", "none found")]
    bad = []
    for t in templates:
        try:
            with open(t) as f:
                json.load(f)
        except Exception as e:
            bad.append(f"{t.name}: {e}")
    if bad:
        return [_row(FAIL, "workflow templates", "; ".join(bad))]
    return [_row(OK, "workflow templates", f"{len(templates)} parse OK")]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=None, help="Workspace path. Default: ${PWD}/n8n-harness-workspace, or ${PWD} if its basename is already n8n-harness-workspace.")
    parser.add_argument("--env", default=None, help="Check a specific env (default: all configured envs)")
    args = parser.parse_args()

    ws = workspace_root(args.workspace)
    rows: list[tuple] = []
    rows += _check_workspace(ws)

    config_dir = ws / "n8n-config"
    envs: list[str] = []
    if args.env:
        envs = [args.env]
    elif config_dir.is_dir():
        envs = [
            p.stem for p in sorted(config_dir.glob("*.yml"))
            if p.stem not in ("common", "deployment_order")
        ]

    if not envs:
        rows.append(_row(WARN, "environments", "no env configured — run bootstrap-env first"))
    else:
        for env in envs:
            rows += _check_env_yaml(ws, env)
            rows += _check_n8n_api(ws, env)

    rows += _check_templates(ws)

    print("\nn8n-harness doctor report:")
    for state, label, detail in rows:
        print(_fmt(state, label, detail))
    print()

    if any(state == FAIL for state, _, _ in rows):
        sys.exit(1)


if __name__ == "__main__":
    main()
