#!/usr/bin/env python3
"""
UUID placeholder resolver for n8n workflow trigger nodes.

Handles {{HYDRATE:uuid:identifier}} placeholders that generate fresh UUIDs
during hydration and are restored during dehydration.

Usage (Hydration):
    from uuid_hydrator import resolve_uuid_placeholders
    workflow = resolve_uuid_placeholders(workflow)

Usage (Dehydration):
    from uuid_hydrator import dehydrate_trigger_uuids
    workflow, count = dehydrate_trigger_uuids(workflow)
"""

import re
import uuid
from typing import Any, Dict, List, Set, Tuple


# Pattern to match {{HYDRATE:uuid:identifier}} placeholders
UUID_PLACEHOLDER_PATTERN = re.compile(r'\{\{HYDRATE:uuid:([a-zA-Z0-9_-]+)\}\}')

# Standard UUID v4 pattern
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)

# Entry-point trigger node types that should have UUIDs dehydrated
ENTRY_POINT_TRIGGERS = {
    '@n8n/n8n-nodes-langchain.chatTrigger',
    'n8n-nodes-base.executeWorkflowTrigger',
    'n8n-nodes-base.manualTrigger',
    'n8n-nodes-base.scheduleTrigger',
    'n8n-nodes-base.webhookTrigger',
}

# UUID fields in trigger nodes
UUID_FIELDS = ['id', 'webhookId']


def _is_uuid(value: str) -> bool:
    """Check if a string is a valid UUID v4 format."""
    if not isinstance(value, str):
        return False
    return bool(UUID_PATTERN.match(value))


def _sanitize_identifier(name: str) -> str:
    """Convert a node name to a valid placeholder identifier."""
    identifier = name.lower()
    identifier = re.sub(r'[\s_]+', '-', identifier)
    identifier = re.sub(r'[^a-z0-9-]', '', identifier)
    identifier = identifier.strip('-')
    identifier = re.sub(r'-+', '-', identifier)
    return identifier or 'node'


def find_uuid_placeholders(data: Any) -> List[str]:
    """Find all {{HYDRATE:uuid:...}} placeholders in workflow data."""
    placeholders: Set[str] = set()

    def _search(obj: Any):
        if isinstance(obj, dict):
            for value in obj.values():
                _search(value)
        elif isinstance(obj, list):
            for item in obj:
                _search(item)
        elif isinstance(obj, str):
            for match in UUID_PLACEHOLDER_PATTERN.finditer(obj):
                placeholders.add(match.group(1))

    _search(data)
    return sorted(placeholders)


def resolve_uuid_placeholders(
    data: Any,
    uuid_cache: Dict[str, str] = None
) -> Any:
    """
    Recursively resolve {{HYDRATE:uuid:identifier}} placeholders with fresh UUIDs.

    Uses a cache to ensure the same identifier always resolves to the same UUID
    within a single hydration run.
    """
    if uuid_cache is None:
        uuid_cache = {}

    if isinstance(data, dict):
        return {
            key: resolve_uuid_placeholders(value, uuid_cache)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [
            resolve_uuid_placeholders(item, uuid_cache)
            for item in data
        ]
    elif isinstance(data, str):
        return _resolve_string_uuid_placeholders(data, uuid_cache)
    else:
        return data


def _resolve_string_uuid_placeholders(text: str, uuid_cache: Dict[str, str]) -> str:
    """Resolve all {{HYDRATE:uuid:...}} placeholders in a string."""
    def replace_match(match: re.Match) -> str:
        identifier = match.group(1)
        if identifier not in uuid_cache:
            uuid_cache[identifier] = str(uuid.uuid4())
        return uuid_cache[identifier]

    return UUID_PLACEHOLDER_PATTERN.sub(replace_match, text)


def dehydrate_trigger_uuids(workflow: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    """
    Replace UUIDs in trigger nodes with {{HYDRATE:uuid:...}} placeholders.

    This is the reverse of resolve_uuid_placeholders.
    """
    replacement_count = 0

    for node in workflow.get('nodes', []):
        node_type = node.get('type', '')

        if node_type not in ENTRY_POINT_TRIGGERS:
            continue

        node_name = node.get('name', 'trigger')
        sanitized_name = _sanitize_identifier(node_name)

        for field in UUID_FIELDS:
            if field not in node:
                continue

            value = node[field]
            if _is_uuid(value):
                placeholder = f"{{{{HYDRATE:uuid:{sanitized_name}-{field}}}}}"
                node[field] = placeholder
                replacement_count += 1

    return workflow, replacement_count


def dehydrate_uuids_from_template(
    workflow: Dict[str, Any],
    template: Dict[str, Any]
) -> Tuple[Dict[str, Any], int]:
    """
    Restore UUID placeholders for non-trigger nodes based on an existing template.

    Matches template nodes to workflow nodes by name and restores placeholders.
    """
    replacement_count = 0

    template_placeholders: Dict[str, Dict[str, str]] = {}

    for template_node in template.get('nodes', []):
        node_name = template_node.get('name')
        if not node_name:
            continue

        for field in UUID_FIELDS:
            if field not in template_node:
                continue

            value = template_node[field]
            if isinstance(value, str) and UUID_PLACEHOLDER_PATTERN.match(value):
                if node_name not in template_placeholders:
                    template_placeholders[node_name] = {}
                template_placeholders[node_name][field] = value

    for node in workflow.get('nodes', []):
        node_name = node.get('name')
        if not node_name or node_name not in template_placeholders:
            continue

        for field, placeholder in template_placeholders[node_name].items():
            if field not in node:
                continue

            value = node[field]
            if _is_uuid(value):
                node[field] = placeholder
                replacement_count += 1

    return workflow, replacement_count


# CLI for testing
if __name__ == '__main__':
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python uuid_hydrator.py <workflow_file> [--dehydrate | --hydrate | --summary]")
        sys.exit(1)

    workflow_file = sys.argv[1]
    action = sys.argv[2] if len(sys.argv) > 2 else '--summary'

    try:
        with open(workflow_file, 'r') as f:
            workflow = json.load(f)

        if action == '--summary':
            placeholders = find_uuid_placeholders(workflow)
            print(f"\nFound {len(placeholders)} UUID placeholder(s): {placeholders}")

        elif action == '--dehydrate':
            workflow, count = dehydrate_trigger_uuids(workflow)
            print(f"\nDehydrated {count} UUID field(s)")
            print(json.dumps(workflow, indent=2))

        elif action == '--hydrate':
            placeholders = find_uuid_placeholders(workflow)
            print(f"\nFound {len(placeholders)} UUID placeholders: {placeholders}")
            workflow = resolve_uuid_placeholders(workflow)
            print(json.dumps(workflow, indent=2))

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error: {e}")
        sys.exit(1)
