#!/usr/bin/env python3
"""
JavaScript placeholder resolver for n8n workflows.

Resolves {{HYDRATE:js:path}} placeholders in workflow JSON by loading JS files
and wrapping them with DEHYDRATE markers.

Hydration:
    {{HYDRATE:js:common/functions/process_excel_data.js}}

    return processExcelData($input.item.json.data);

Becomes:
    // {{DEHYDRATE:js:common/functions/process_excel_data.js:start}}
    function processExcelData(data) {
      // ... full file content ...
    }
    // {{DEHYDRATE:js:common/functions/process_excel_data.js:end}}

    return processExcelData($input.item.json.data);

Dehydration reverses this by detecting DEHYDRATE markers and restoring
HYDRATE placeholders.

Usage (Hydration):
    from js_hydrator import resolve_js_placeholders
    workflow = resolve_js_placeholders(workflow, base_dir)

Usage (Dehydration):
    from js_hydrator import dehydrate_js_placeholder
    dehydrated_code = dehydrate_js_placeholder(js_code)
"""

import re
from pathlib import Path
from typing import Any, List, Set

# Pattern to match {{HYDRATE:js:path}} placeholders
JS_PLACEHOLDER_PATTERN = re.compile(r'\{\{HYDRATE:js:([^}]+)\}\}')

# Pattern to match DEHYDRATE markers wrapping JS content
JS_DEHYDRATE_PATTERN = re.compile(
    r'// \{\{DEHYDRATE:js:([^:}]+):start\}\}\n(.*?)\n// \{\{DEHYDRATE:js:\1:end\}\}',
    re.DOTALL
)


def find_js_placeholders(data: Any) -> List[str]:
    """Find all {{HYDRATE:js:...}} placeholders in workflow data."""
    placeholders: Set[str] = set()

    def _search(obj: Any):
        if isinstance(obj, dict):
            for value in obj.values():
                _search(value)
        elif isinstance(obj, list):
            for item in obj:
                _search(item)
        elif isinstance(obj, str):
            for match in JS_PLACEHOLDER_PATTERN.finditer(obj):
                placeholders.add(match.group(1))

    _search(data)
    return sorted(placeholders)


def resolve_js_placeholders(data: Any, base_dir: Path) -> Any:
    """
    Recursively resolve {{HYDRATE:js:path}} placeholders in workflow data.

    Loads the JS file, wraps it with DEHYDRATE markers, and replaces the
    placeholder in-place.
    """
    if isinstance(data, dict):
        return {
            key: resolve_js_placeholders(value, base_dir)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [
            resolve_js_placeholders(item, base_dir)
            for item in data
        ]
    elif isinstance(data, str):
        return _resolve_string_js_placeholders(data, base_dir)
    else:
        return data


def _resolve_string_js_placeholders(text: str, base_dir: Path) -> str:
    """Resolve all {{HYDRATE:js:...}} placeholders in a string."""
    def replace_match(match: re.Match) -> str:
        file_path = match.group(1)
        js_file = base_dir / file_path

        if not js_file.exists():
            raise FileNotFoundError(f"JS file not found: {js_file}")

        content = js_file.read_text()

        start_marker = f"// {{{{DEHYDRATE:js:{file_path}:start}}}}"
        end_marker = f"// {{{{DEHYDRATE:js:{file_path}:end}}}}"

        return f"{start_marker}\n{content}\n{end_marker}"

    return JS_PLACEHOLDER_PATTERN.sub(replace_match, text)


def dehydrate_js_placeholder(js_code: str) -> str:
    """
    Detect DEHYDRATE markers in JS code and restore HYDRATE placeholders.

    Finds patterns like:
        // {{DEHYDRATE:js:path:start}}
        ... content ...
        // {{DEHYDRATE:js:path:end}}

    And replaces them with:
        {{HYDRATE:js:path}}
    """
    def replace_match(match: re.Match) -> str:
        file_path = match.group(1)
        return f"{{{{HYDRATE:js:{file_path}}}}}"

    return JS_DEHYDRATE_PATTERN.sub(replace_match, js_code)


# CLI for testing
if __name__ == '__main__':
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python js_hydrator.py <workflow_file> [--base-dir <dir>] [--resolve]")
        sys.exit(1)

    workflow_file = sys.argv[1]
    base_dir = Path(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[2] == '--base-dir' else Path(__file__).parent.parent.parent

    try:
        with open(workflow_file, 'r') as f:
            workflow = json.load(f)

        placeholders = find_js_placeholders(workflow)
        print(f"\nFound {len(placeholders)} JS placeholder(s):")
        for p in placeholders:
            print(f"  {{{{HYDRATE:js:{p}}}}}")

        if '--resolve' in sys.argv:
            resolved = resolve_js_placeholders(workflow, base_dir)
            print("\nResolved workflow:")
            print(json.dumps(resolved, indent=2))

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error: {e}")
        sys.exit(1)
