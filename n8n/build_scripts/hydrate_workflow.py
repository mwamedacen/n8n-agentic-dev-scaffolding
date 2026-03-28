#!/usr/bin/env python3
"""
Generic workflow hydrator - replaces per-workflow hydrate scripts.

Hydrates a single workflow template by resolving all placeholder types:
1. {{HYDRATE:txt:path}}  - Text file content (prompts)
2. {{HYDRATE:json:path}} - JSON schema content
3. {{HYDRATE:html:path}} - HTML/email template content
4. {{HYDRATE:js:path}}   - JavaScript file content (with DEHYDRATE markers)
5. {{HYDRATE:env:key}}   - Environment config values
6. {{HYDRATE:uuid:id}}   - Fresh UUIDs for trigger nodes

Usage:
    python3 hydrate_workflow.py -e dev -t n8n/workflows/periodic_excel_report.template.json -k periodic_excel_report
    python3 hydrate_workflow.py -e prod -t n8n/workflows/my_workflow.template.json -k my_workflow
"""

import json
import sys
import argparse
from pathlib import Path

from env_config import load_env_config, get_config_value, list_available_environments
from env_hydrator import resolve_env_placeholders, find_env_placeholders
from file_hydrator import resolve_file_placeholders, find_file_placeholders
from js_hydrator import resolve_js_placeholders, find_js_placeholders
from uuid_hydrator import resolve_uuid_placeholders, find_uuid_placeholders
from hydrate_validator import validate_no_placeholders


def hydrate_workflow(
    template_path: Path,
    workflow_key: str,
    env_config: dict,
    base_dir: Path,
    output_dir: Path
) -> Path:
    """
    Hydrate a single workflow template.

    Args:
        template_path: Path to the .template.json file
        workflow_key: Workflow key in the environment config
        env_config: Loaded environment configuration
        base_dir: Project root directory
        output_dir: Directory to save generated workflow

    Returns:
        Path to the generated workflow file
    """
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    # Load template
    with open(template_path, 'r') as f:
        workflow = json.load(f)

    # 1. Resolve file placeholders (txt, json, html)
    file_placeholders = find_file_placeholders(workflow)
    if file_placeholders:
        print(f"  Resolving {len(file_placeholders)} file placeholder(s) (txt/json/html)...")
        workflow = resolve_file_placeholders(workflow, base_dir)

    # 2. Resolve JS placeholders
    js_placeholders = find_js_placeholders(workflow)
    if js_placeholders:
        print(f"  Resolving {len(js_placeholders)} JS placeholder(s)...")
        workflow = resolve_js_placeholders(workflow, base_dir)

    # 3. Resolve ENV placeholders
    env_placeholders = find_env_placeholders(workflow)
    if env_placeholders:
        print(f"  Resolving {len(env_placeholders)} ENV placeholder(s)...")
        workflow = resolve_env_placeholders(workflow, env_config)

    # 4. Resolve UUID placeholders
    uuid_placeholders = find_uuid_placeholders(workflow)
    if uuid_placeholders:
        print(f"  Resolving {len(uuid_placeholders)} UUID placeholder(s)...")
        workflow = resolve_uuid_placeholders(workflow)

    # 5. Set workflow name with environment postfix
    workflow_config = get_config_value(env_config, f'workflows.{workflow_key}')
    if workflow_config and workflow_config.get('name'):
        base_name = workflow_config['name']
        postfix = env_config.get('workflowNamePostfix', '')
        workflow['name'] = f"{base_name}{postfix}"
        print(f"  Workflow name: {workflow['name']}")

    # 6. Save generated workflow
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f'{workflow_key}.generated.json'

    with open(output_path, 'w') as f:
        json.dump(workflow, f, indent=2)

    # 7. Validate no unresolved placeholders
    validate_no_placeholders(output_path, workflow)

    return output_path


def main():
    """Main function - hydrate a single workflow."""
    parser = argparse.ArgumentParser(
        description='Hydrate a workflow template for a specific environment'
    )
    parser.add_argument(
        '-e', '--env',
        required=True,
        help=f'Environment name ({", ".join(list_available_environments())})'
    )
    parser.add_argument(
        '-t', '--template',
        required=True,
        help='Path to template file (relative to project root or absolute)'
    )
    parser.add_argument(
        '-k', '--key',
        required=True,
        help='Workflow key in environment config (e.g., periodic_excel_report)'
    )
    args = parser.parse_args()

    # Load environment config
    try:
        env_config = load_env_config(args.env)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading environment config: {e}")
        sys.exit(1)

    base_dir = Path(__file__).parent.parent.parent
    template_path = Path(args.template)

    # Handle relative paths
    if not template_path.is_absolute():
        template_path = base_dir / template_path

    output_dir = base_dir / 'n8n' / 'workflows' / 'generated' / args.env

    print("=" * 70)
    print(f"Hydrating [{args.key}] for [{env_config['displayName']}]")
    print("=" * 70)
    print()

    try:
        output_path = hydrate_workflow(
            template_path=template_path,
            workflow_key=args.key,
            env_config=env_config,
            base_dir=base_dir,
            output_dir=output_dir
        )

        print()
        print("=" * 70)
        print(f"Workflow generated for [{env_config['displayName']}]!")
        print(f"   Output: {output_path}")
        print("=" * 70)

    except (FileNotFoundError, ValueError) as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
