#!/usr/bin/env python3
"""
File-based placeholder resolver for n8n workflows.

Handles three placeholder types that load content from files:
- {{HYDRATE:txt:path}}  -> Raw text content (prompts, instructions)
- {{HYDRATE:json:path}} -> JSON file content (schemas, configs)
- {{HYDRATE:html:path}} -> HTML/text template content (emails)

Usage (Hydration):
    from file_hydrator import resolve_file_placeholders
    workflow = resolve_file_placeholders(workflow, base_dir)

Usage (Dehydration):
    from file_hydrator import dehydrate_txt_placeholder, dehydrate_json_placeholder, dehydrate_html_placeholder
"""

import re
import json
from pathlib import Path
from typing import Any, Dict, List, Set

# Combined pattern for all file-based placeholder types
FILE_PLACEHOLDER_PATTERN = re.compile(r'\{\{HYDRATE:(txt|json|html):([^}]+)\}\}')

# Individual patterns
TXT_PLACEHOLDER_PATTERN = re.compile(r'\{\{HYDRATE:txt:([^}]+)\}\}')
JSON_PLACEHOLDER_PATTERN = re.compile(r'\{\{HYDRATE:json:([^}]+)\}\}')
HTML_PLACEHOLDER_PATTERN = re.compile(r'\{\{HYDRATE:html:([^}]+)\}\}')


def find_file_placeholders(data: Any) -> List[dict]:
    """
    Find all file-based placeholders in workflow data.

    Returns:
        List of dicts with 'type' and 'path' keys
    """
    placeholders: list = []
    seen: Set[str] = set()

    def _search(obj: Any):
        if isinstance(obj, dict):
            for value in obj.values():
                _search(value)
        elif isinstance(obj, list):
            for item in obj:
                _search(item)
        elif isinstance(obj, str):
            for match in FILE_PLACEHOLDER_PATTERN.finditer(obj):
                key = f"{match.group(1)}:{match.group(2)}"
                if key not in seen:
                    seen.add(key)
                    placeholders.append({
                        'type': match.group(1),
                        'path': match.group(2)
                    })

    _search(data)
    return sorted(placeholders, key=lambda x: f"{x['type']}:{x['path']}")


def resolve_file_placeholders(data: Any, base_dir: Path) -> Any:
    """
    Recursively resolve {{HYDRATE:txt/json/html:path}} placeholders.

    Args:
        data: Workflow data (dict, list, or string)
        base_dir: Project root directory for resolving file paths

    Returns:
        Data with all file placeholders resolved
    """
    if isinstance(data, dict):
        return {
            key: resolve_file_placeholders(value, base_dir)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [
            resolve_file_placeholders(item, base_dir)
            for item in data
        ]
    elif isinstance(data, str):
        return _resolve_string_file_placeholders(data, base_dir)
    else:
        return data


def _resolve_string_file_placeholders(text: str, base_dir: Path) -> str:
    """Resolve all file-based placeholders in a string."""
    def replace_match(match: re.Match) -> str:
        file_type = match.group(1)
        file_path = match.group(2)
        full_path = base_dir / file_path

        if not full_path.exists():
            raise FileNotFoundError(f"{file_type.upper()} file not found: {full_path}")

        if file_type == 'txt':
            return full_path.read_text().strip()

        elif file_type == 'json':
            # Load JSON and re-serialize as a string
            # This handles the json_schema wrapper format
            with open(full_path, 'r') as f:
                json_content = json.load(f)
            return json.dumps(json_content)

        elif file_type == 'html':
            return full_path.read_text().strip()

        return match.group(0)

    return FILE_PLACEHOLDER_PATTERN.sub(replace_match, text)


# --- Dehydration functions ---

def dehydrate_txt_placeholder(value: str, base_dir: Path) -> str:
    """Match prompt content to source file and restore {{HYDRATE:txt:path}} placeholder."""
    prompt_dir = base_dir / 'common' / 'prompts'
    if not prompt_dir.exists():
        return value

    for prompt_file in prompt_dir.glob('*_prompt.txt'):
        with open(prompt_file, 'r') as f:
            prompt_content = f.read().strip()

        if value.strip() == prompt_content:
            rel_path = prompt_file.relative_to(base_dir)
            return f"{{{{HYDRATE:txt:{rel_path}}}}}"

    return value


def dehydrate_json_placeholder(value: Any, base_dir: Path) -> Any:
    """
    Match JSON schema content to source file and restore {{HYDRATE:json:path}} placeholder.

    Detects the json_schema wrapper format:
    {"type": "json_schema", "name": "...", "schema": {...}, "strict": true}
    """
    if isinstance(value, str):
        try:
            value_parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    else:
        value_parsed = value

    if not isinstance(value_parsed, dict):
        return value

    schema_dir = base_dir / 'common' / 'prompts'
    if not schema_dir.exists():
        return value

    for schema_file in schema_dir.glob('*_schema.json'):
        with open(schema_file, 'r') as f:
            file_content = json.load(f)

        # Compare the full JSON content
        if value_parsed == file_content:
            rel_path = schema_file.relative_to(base_dir)
            return f"{{{{HYDRATE:json:{rel_path}}}}}"

        # Also try comparing just the schema part if wrapped
        if value_parsed.get('type') == 'json_schema':
            file_schema = file_content.get('schema', file_content)
            if value_parsed.get('schema') == file_schema:
                rel_path = schema_file.relative_to(base_dir)
                return f"{{{{HYDRATE:json:{rel_path}}}}}"

    return value


def dehydrate_html_placeholder(message: str, base_dir: Path) -> str:
    """Match message against email templates and restore {{HYDRATE:html:path}} placeholder."""
    templates_dir = base_dir / 'common' / 'templates'
    if not templates_dir.exists():
        return message

    for template_file in templates_dir.glob('*.template.txt'):
        template_path = str(template_file.relative_to(base_dir))

        with open(template_file, 'r') as f:
            content = f.read().strip()

        # Compare with message (strip whitespace for comparison)
        message_cleaned = message.lstrip('=').strip()

        if message_cleaned == content:
            return f"={{{{HYDRATE:html:{template_path}}}}}"

    return message


# CLI for testing
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python file_hydrator.py <workflow_file> [--base-dir <dir>] [--resolve]")
        sys.exit(1)

    workflow_file = sys.argv[1]
    base_dir = Path(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[2] == '--base-dir' else Path(__file__).parent.parent.parent

    try:
        with open(workflow_file, 'r') as f:
            workflow = json.load(f)

        placeholders = find_file_placeholders(workflow)
        print(f"\nFound {len(placeholders)} file placeholder(s):")
        for p in placeholders:
            print(f"  {{{{HYDRATE:{p['type']}:{p['path']}}}}}")

        if '--resolve' in sys.argv:
            resolved = resolve_file_placeholders(workflow, base_dir)
            print("\nResolved workflow:")
            print(json.dumps(resolved, indent=2))

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error: {e}")
        sys.exit(1)
