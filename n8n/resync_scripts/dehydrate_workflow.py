#!/usr/bin/env python3
"""
Dehydrate a workflow - reverse the hydration process to produce a template.

Converts a live n8n workflow back into a template by:
1. Removing n8n metadata (id, versionId, createdAt, updatedAt, etc.)
2. Replacing trigger node UUIDs with {{HYDRATE:uuid:...}} placeholders
3. Restoring template UUIDs from existing template (if available)
4. Replacing environment-specific values with {{HYDRATE:env:...}} placeholders
5. Restoring file content with {{HYDRATE:txt/json/html/js:...}} placeholders

Usage:
    python3 dehydrate_workflow.py --workflow-file fetched.json --output template.json --env dev
    python3 dehydrate_workflow.py --workflow-file fetched.json --output template.json --env dev --remove-triggers
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Add build_scripts to path for importing hydrator modules
SCRIPT_DIR = Path(__file__).parent
BUILD_SCRIPTS_DIR = SCRIPT_DIR.parent / 'build_scripts'
sys.path.insert(0, str(BUILD_SCRIPTS_DIR))

from js_hydrator import dehydrate_js_placeholder
from file_hydrator import dehydrate_txt_placeholder, dehydrate_json_placeholder, dehydrate_html_placeholder
from uuid_hydrator import dehydrate_trigger_uuids, dehydrate_uuids_from_template, UUID_PLACEHOLDER_PATTERN
from env_config import load_env_config, flatten_config


# n8n metadata keys to strip from the workflow.
# Aligned with helpers.workflow_semantic_diff's _DIFF_IGNORE list so resync
# round-trips byte-stable on n8n cloud.
METADATA_KEYS_TO_REMOVE = [
    'id',
    'versionId',
    'createdAt',
    'updatedAt',
    'active',
    'staticData',
    'pinData',
    'tags',
    'shared',
    'homeProject',
    'usedCredentials',
    'isArchived',
    'description',
    'activeVersion',
    'activeVersionId',
    'triggerCount',
    'versionCounter',
    'scopes',
    'parentFolder',
    'meta',
]

# Trigger node types that can be optionally removed
TRIGGER_NODE_TYPES = {
    'n8n-nodes-base.scheduleTrigger',
    'n8n-nodes-base.webhookTrigger',
    'n8n-nodes-base.manualTrigger',
    '@n8n/n8n-nodes-langchain.chatTrigger',
    'n8n-nodes-base.executeWorkflowTrigger',
}


def clean_workflow(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove n8n metadata from workflow, keeping nodes, connections, and meta.

    Args:
        workflow: Raw workflow from n8n API

    Returns:
        Cleaned workflow with only essential keys
    """
    cleaned = {}

    for key, value in workflow.items():
        if key in METADATA_KEYS_TO_REMOVE:
            continue
        cleaned[key] = value

    return cleaned


def remove_trigger_nodes(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove trigger nodes from the workflow.

    Removes the nodes and cleans up connections referencing them.
    """
    trigger_names = set()
    remaining_nodes = []

    for node in workflow.get('nodes', []):
        if node.get('type', '') in TRIGGER_NODE_TYPES:
            trigger_names.add(node.get('name', ''))
        else:
            remaining_nodes.append(node)

    workflow['nodes'] = remaining_nodes

    # Clean up connections that reference removed triggers
    connections = workflow.get('connections', {})
    cleaned_connections = {}
    for source_name, targets in connections.items():
        if source_name not in trigger_names:
            cleaned_connections[source_name] = targets

    workflow['connections'] = cleaned_connections

    return workflow


def dehydrate_trigger_uuids_wrapper(workflow: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    """Replace UUIDs in trigger nodes with placeholders."""
    return dehydrate_trigger_uuids(workflow)


def dehydrate_template_uuids(
    workflow: Dict[str, Any],
    template_path: Path
) -> Tuple[Dict[str, Any], int]:
    """
    Restore UUID placeholders for non-trigger nodes based on existing template.

    If a template file exists, matches nodes by name and restores their
    UUID placeholders.
    """
    if not template_path.exists():
        return workflow, 0

    with open(template_path, 'r') as f:
        template = json.load(f)

    return dehydrate_uuids_from_template(workflow, template)


def dehydrate_env_placeholders(
    workflow: Dict[str, Any],
    env_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Replace environment-specific values with {{HYDRATE:env:...}} placeholders.

    Builds a value-to-key mapping from the flattened config and replaces
    the longest values first to avoid partial replacements.
    """
    flat = flatten_config(env_config)

    # Build value -> key mapping, filtering short/numeric values
    value_to_key = {}
    for key, value in flat.items():
        str_value = str(value)
        # Only replace values that are meaningful (not too short, not pure numbers)
        if len(str_value) >= 3 and not str_value.isdigit():
            value_to_key[str_value] = key

    if not value_to_key:
        return workflow

    # Sort by value length descending to replace longest matches first
    sorted_replacements = sorted(
        value_to_key.items(),
        key=lambda x: len(x[0]),
        reverse=True
    )

    def replace_in_value(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: replace_in_value(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_in_value(item) for item in obj]
        elif isinstance(obj, str):
            result = obj
            for value, key in sorted_replacements:
                if value in result:
                    placeholder = f"{{{{HYDRATE:env:{key}}}}}"
                    result = result.replace(value, placeholder)
            return result
        return obj

    return replace_in_value(workflow)


def dehydrate_file_content(workflow: Dict[str, Any], base_dir: Path) -> Dict[str, Any]:
    """
    Restore file-based placeholders (txt, json, html) in workflow nodes.

    Processes:
    - Code nodes: jsCode, pythonCode fields
    - Set nodes: assignment values
    - Gmail/email nodes: message field
    """
    for node in workflow.get('nodes', []):
        node_type = node.get('type', '')
        params = node.get('parameters', {})

        # --- Code nodes: JS ---
        if 'jsCode' in params:
            params['jsCode'] = dehydrate_js_placeholder(params['jsCode'])

        # --- Code nodes: Python ---
        if 'pythonCode' in params:
            params['pythonCode'] = dehydrate_txt_placeholder(params['pythonCode'], base_dir)

        # --- Set nodes: assignments ---
        if 'assignments' in params:
            assignments = params['assignments']
            if isinstance(assignments, dict) and 'assignments' in assignments:
                for assignment in assignments['assignments']:
                    value = assignment.get('value', '')
                    if isinstance(value, str) and len(value) > 50:
                        # Try txt dehydration
                        dehydrated = dehydrate_txt_placeholder(value, base_dir)
                        if dehydrated != value:
                            assignment['value'] = dehydrated
                            continue

                        # Try json dehydration
                        dehydrated = dehydrate_json_placeholder(value, base_dir)
                        if dehydrated != value:
                            assignment['value'] = dehydrated
                            continue

        # --- Gmail/email nodes: message ---
        if 'message' in params:
            message = params['message']
            if isinstance(message, str) and len(message) > 50:
                dehydrated = dehydrate_html_placeholder(message, base_dir)
                if dehydrated != message:
                    params['message'] = dehydrated

    return workflow


def dehydrate_workflow(
    workflow: Dict[str, Any],
    env_name: str,
    base_dir: Path,
    output_path: Path,
    remove_triggers: bool = False
) -> Dict[str, Any]:
    """
    Orchestrate all dehydration steps.

    Order of operations:
    1. Clean metadata
    2. Replace trigger UUIDs
    3. Restore template UUIDs (if template exists)
    4. Replace environment values
    5. Restore file content placeholders

    Args:
        workflow: Raw workflow from n8n API
        env_name: Environment name for loading config
        base_dir: Project root directory
        output_path: Where the template will be saved (used to find existing template)
        remove_triggers: Whether to remove trigger nodes entirely

    Returns:
        Dehydrated workflow ready to save as template
    """
    # Load environment config
    env_config = load_env_config(env_name)

    print(f"  Dehydrating workflow for [{env_config.get('displayName', env_name)}]")

    # 1. Clean n8n metadata
    workflow = clean_workflow(workflow)
    print("    Cleaned n8n metadata")

    # Remove triggers if requested
    if remove_triggers:
        workflow = remove_trigger_nodes(workflow)
        print("    Removed trigger nodes")

    # 2. Restore template UUIDs FIRST — preserves original placeholder names for
    #    nodes (including triggers) that already have a placeholder in the template.
    workflow, template_uuid_count = dehydrate_template_uuids(workflow, output_path)
    if template_uuid_count > 0:
        print(f"    Restored {template_uuid_count} template UUID(s)")

    # 3. Auto-generate trigger UUID placeholders for any trigger node not already
    #    covered by template restoration.
    workflow, trigger_uuid_count = dehydrate_trigger_uuids_wrapper(workflow)
    if trigger_uuid_count > 0:
        print(f"    Dehydrated {trigger_uuid_count} trigger UUID(s)")

    # 4. Replace environment-specific values
    workflow = dehydrate_env_placeholders(workflow, env_config)
    print("    Dehydrated environment placeholders")

    # 5. Restore file content placeholders
    workflow = dehydrate_file_content(workflow, base_dir)
    print("    Dehydrated file content placeholders")

    return workflow


def main():
    parser = argparse.ArgumentParser(
        description='Dehydrate a workflow from n8n back to a template'
    )
    parser.add_argument(
        '--workflow-file',
        required=True,
        help='Path to the fetched workflow JSON file'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Output path for the dehydrated template'
    )
    parser.add_argument(
        '--base-dir',
        default=None,
        help='Project root directory (default: auto-detect)'
    )
    parser.add_argument(
        '--env',
        required=True,
        help='Environment name for loading config'
    )
    parser.add_argument(
        '--remove-triggers',
        action='store_true',
        help='Remove trigger nodes from the template'
    )
    args = parser.parse_args()

    # Resolve paths
    if args.base_dir:
        base_dir = Path(args.base_dir)
    else:
        base_dir = SCRIPT_DIR.parent.parent

    workflow_file = Path(args.workflow_file)
    output_path = Path(args.output)

    # Handle relative output path
    if not output_path.is_absolute():
        output_path = base_dir / output_path

    # Load the fetched workflow
    if not workflow_file.exists():
        print(f"Error: Workflow file not found: {workflow_file}")
        sys.exit(1)

    with open(workflow_file, 'r') as f:
        workflow = json.load(f)

    print("=" * 60)
    print(f"Dehydrating Workflow")
    print("=" * 60)
    print(f"  Source: {workflow_file}")
    print(f"  Output: {output_path}")
    print(f"  Environment: {args.env}")
    print(f"  Remove triggers: {args.remove_triggers}")
    print()

    try:
        dehydrated = dehydrate_workflow(
            workflow=workflow,
            env_name=args.env,
            base_dir=base_dir,
            output_path=output_path,
            remove_triggers=args.remove_triggers
        )

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save dehydrated template
        with open(output_path, 'w') as f:
            json.dump(dehydrated, f, indent=2)

        print()
        print("=" * 60)
        print(f"Template saved: {output_path}")
        print("=" * 60)

    except Exception as e:
        print(f"\nError during dehydration: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
