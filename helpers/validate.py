#!/usr/bin/env python3
"""Structural validation for a workflow template or generated JSON."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from helpers.workspace import workspace_root
from helpers.placeholder import validator as placeholder_validator


def validate_workflow_json(text: str, source: str = "template") -> tuple[bool, list[str]]:
    """Run structural REST validation. Returns (is_valid, errors)."""
    errors: list[str] = []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return (False, [f"JSON parse error: {e}"])

    if not isinstance(data, dict):
        return (False, ["top-level value is not a JSON object"])

    if "nodes" not in data:
        errors.append("missing top-level 'nodes' key")
    elif not isinstance(data["nodes"], list):
        errors.append("'nodes' must be a list")
    else:
        for i, node in enumerate(data["nodes"]):
            if not isinstance(node, dict):
                errors.append(f"node {i} is not an object")
                continue
            for required in ("name", "type", "parameters"):
                if required not in node:
                    errors.append(f"node {i} missing '{required}'")

    if "connections" not in data:
        errors.append("missing top-level 'connections' key")
    elif not isinstance(data["connections"], dict):
        errors.append("'connections' must be an object keyed by node name")

    if source == "template":
        if "pinData" in data and data["pinData"]:
            errors.append("template contains pinData (forbidden in templates)")

    if source == "built":
        residuals = placeholder_validator.check_residuals(text)
        if residuals:
            errors.append(f"residual placeholders in built JSON: {residuals}")

    return (len(errors) == 0, errors)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--workflow-key", required=True, dest="workflow_key")
    parser.add_argument("--env", default=None)
    parser.add_argument("--source", choices=("built", "template"), default=None,
                        help="Default: 'built' if --env given, else 'template'")
    args = parser.parse_args()

    ws = workspace_root(args.workspace)
    source = args.source or ("built" if args.env else "template")

    if source == "built":
        if not args.env:
            print("ERROR: --source built requires --env", file=sys.stderr)
            sys.exit(2)
        path = ws / "n8n-build" / args.env / f"{args.workflow_key}.generated.json"
    else:
        path = ws / "n8n-workflows-template" / f"{args.workflow_key}.template.json"

    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    valid, errors = validate_workflow_json(text, source=source)
    print(json.dumps({"valid": valid, "source": source, "path": str(path), "errors": errors}, indent=2))
    sys.exit(0 if valid else 1)


if __name__ == "__main__":
    main()
