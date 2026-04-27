#!/usr/bin/env python3
"""Structural validation for a workflow template or generated JSON."""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from helpers.workspace import workspace_root
from helpers.placeholder import validator as placeholder_validator


_JS_PLACEHOLDER_RE = re.compile(r"\{\{HYDRATE:js:([^}]+)\}\}")
_PY_PLACEHOLDER_RE = re.compile(r"\{\{HYDRATE:py:([^}]+)\}\}")
_JS_TRAILER_REQUIRED = 'if (typeof module !== "undefined")'


def _validate_code_node(
    node: dict,
    index: int,
    workspace: Path | None,
) -> list[str]:
    """Return discipline errors for a single n8n-nodes-base.code node (template only)."""
    errors: list[str] = []
    name = node.get("name", f"node[{index}]")
    params = node.get("parameters", {}) or {}

    lang = params.get("language", "javascript")
    if lang == "python":
        code_field_name = "pythonCode"
        ext = "py"
        placeholder_re = _PY_PLACEHOLDER_RE
        test_filename = lambda stem: f"test_{stem}.py"
    else:
        code_field_name = "jsCode"
        ext = "js"
        placeholder_re = _JS_PLACEHOLDER_RE
        test_filename = lambda stem: f"{stem}.test.js"

    code_field = params.get(code_field_name, "")
    if not code_field:
        errors.append(f"node '{name}': {code_field_name} is empty or missing")
        return errors

    m = placeholder_re.search(code_field)
    if not m:
        errors.append(
            f"node '{name}': no {{{{HYDRATE:{ext}:...}}}} placeholder found in {code_field_name}. "
            f"Extract the pure function to n8n-functions/{ext}/<name>.{ext} and add the placeholder."
        )
        return errors

    if workspace is None:
        return errors

    rel_path = m.group(1).strip()
    fn_file = workspace / rel_path
    if not fn_file.exists():
        errors.append(f"node '{name}': referenced file not found: {rel_path}")
        return errors

    fn_stem = fn_file.stem

    if ext == "js":
        js_text = fn_file.read_text(encoding="utf-8")
        if _JS_TRAILER_REQUIRED not in js_text:
            errors.append(
                f"node '{name}': {rel_path} missing required export trailer "
                f'`if (typeof module !== "undefined") module.exports = {{ <fnName> }};` — '
                "without it, n8n-functions-tests/<name>.test.js cannot import the function."
            )

    test_file = workspace / "n8n-functions-tests" / test_filename(fn_stem)
    if not test_file.exists():
        errors.append(
            f"node '{name}': missing test file {test_file.relative_to(workspace)}. "
            "Create it before deploying."
        )

    return errors


def validate_workflow_json(
    text: str,
    source: str = "template",
    workspace: Path | None = None,
) -> tuple[bool, list[str]]:
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

        for i, node in enumerate(data.get("nodes", [])):
            if not isinstance(node, dict):
                continue
            ntype = node.get("type", "")
            name = node.get("name", f"node[{i}]")
            if ntype == "n8n-nodes-base.function":
                errors.append(
                    f"node '{name}': n8n-nodes-base.function is deprecated and forbidden; "
                    "use n8n-nodes-base.code"
                )
                continue
            if ntype == "n8n-nodes-base.code":
                errors.extend(_validate_code_node(node, i, workspace))

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
    valid, errors = validate_workflow_json(text, source=source, workspace=ws)
    print(json.dumps({"valid": valid, "source": source, "path": str(path), "errors": errors}, indent=2))
    sys.exit(0 if valid else 1)


if __name__ == "__main__":
    main()
