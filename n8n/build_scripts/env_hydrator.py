#!/usr/bin/env python3
"""
Environment placeholder resolver for n8n workflows.

Resolves {{HYDRATE:env:key.subkey}} placeholders in workflow JSON using values
from environment configuration files.

Usage:
    from env_hydrator import resolve_env_placeholders
    from env_config import load_env_config

    config = load_env_config('dev')
    workflow = load_workflow('workflow.json')
    resolved_workflow = resolve_env_placeholders(workflow, config)
"""

import re
import json
from typing import Any, Dict

from env_config import get_config_value, flatten_config


# Pattern to match {{HYDRATE:env:key.subkey}} placeholders
ENV_PLACEHOLDER_PATTERN = re.compile(r'\{\{HYDRATE:env:([a-zA-Z0-9_.]+)\}\}')


def resolve_env_placeholders(
    data: Any,
    config: Dict[str, Any],
    strict: bool = False
) -> Any:
    """
    Recursively resolve {{HYDRATE:env:key}} placeholders in workflow data.

    Args:
        data: Workflow data (dict, list, or string)
        config: Environment configuration dictionary
        strict: If True, raise error for unresolved placeholders

    Returns:
        Data with all HYDRATE:env placeholders resolved

    Raises:
        ValueError: If strict=True and a placeholder cannot be resolved
    """
    if isinstance(data, dict):
        return {
            key: resolve_env_placeholders(value, config, strict)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [
            resolve_env_placeholders(item, config, strict)
            for item in data
        ]
    elif isinstance(data, str):
        return _resolve_string_placeholders(data, config, strict)
    else:
        return data


def _resolve_string_placeholders(
    text: str,
    config: Dict[str, Any],
    strict: bool = False
) -> str:
    """Resolve all {{HYDRATE:env:...}} placeholders in a string."""
    def replace_match(match: re.Match) -> str:
        key_path = match.group(1)
        value = get_config_value(config, key_path)

        if value is None:
            if strict:
                raise ValueError(f"Cannot resolve HYDRATE:env placeholder: {{{{HYDRATE:env:{key_path}}}}}")
            return match.group(0)

        return str(value)

    return ENV_PLACEHOLDER_PATTERN.sub(replace_match, text)


def find_env_placeholders(data: Any) -> list:
    """Find all {{HYDRATE:env:...}} placeholders in workflow data."""
    placeholders = set()

    def _search(obj: Any):
        if isinstance(obj, dict):
            for value in obj.values():
                _search(value)
        elif isinstance(obj, list):
            for item in obj:
                _search(item)
        elif isinstance(obj, str):
            for match in ENV_PLACEHOLDER_PATTERN.finditer(obj):
                placeholders.add(match.group(1))

    _search(data)
    return sorted(placeholders)


def validate_all_placeholders_resolvable(
    data: Any,
    config: Dict[str, Any]
) -> list:
    """Check that all ENV placeholders in data can be resolved."""
    placeholders = find_env_placeholders(data)
    unresolvable = []

    for key_path in placeholders:
        if get_config_value(config, key_path) is None:
            unresolvable.append(key_path)

    return unresolvable


def create_env_placeholder_mapping(config: Dict[str, Any]) -> Dict[str, str]:
    """Create a mapping from config values to their key paths (for dehydration)."""
    flat = flatten_config(config)
    return {
        str(value): key
        for key, value in flat.items()
        if isinstance(value, str) and len(str(value)) > 10
    }


# CLI for testing
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("Usage: python env_hydrator.py <env_name> <workflow_file> [--resolve]")
        sys.exit(1)

    from env_config import load_env_config

    env_name = sys.argv[1]
    workflow_file = sys.argv[2]

    try:
        config = load_env_config(env_name)

        with open(workflow_file, 'r') as f:
            workflow = json.load(f)

        placeholders = find_env_placeholders(workflow)
        unresolvable = validate_all_placeholders_resolvable(workflow, config)

        print(f"\nHYDRATE:env Placeholder Summary")
        print("=" * 50)
        print(f"  Total: {len(placeholders)}")
        print(f"  Resolvable: {len(placeholders) - len(unresolvable)}")
        print(f"  Unresolvable: {len(unresolvable)}")

        for key_path in placeholders:
            value = get_config_value(config, key_path)
            status = "OK" if value is not None else "MISSING"
            print(f"  {{{{HYDRATE:env:{key_path}}}}} [{status}]")

        if '--resolve' in sys.argv:
            resolved = resolve_env_placeholders(workflow, config)
            print("\nResolved workflow:")
            print(json.dumps(resolved, indent=2))

    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)
