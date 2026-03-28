#!/usr/bin/env python3
"""
Master hydration script - auto-discovers and hydrates all workflow templates.

Scans n8n/workflows/ for *.template.json files, extracts workflow keys from
filenames, and hydrates each one for the specified environment.

Usage:
    python3 hydrate_all.py -e dev
    python3 hydrate_all.py -e prod
"""

import sys
import argparse
from pathlib import Path

from env_config import load_env_config, list_available_environments, print_config_summary
from hydrate_workflow import hydrate_workflow


def discover_templates(workflows_dir: Path) -> list:
    """
    Find all *.template.json files and extract workflow keys.

    Convention: {workflow_key}.template.json -> key = workflow_key

    Returns:
        List of (template_path, workflow_key) tuples
    """
    templates = []
    for template_file in sorted(workflows_dir.glob('*.template.json')):
        # Extract key: "periodic_excel_report.template.json" -> "periodic_excel_report"
        key = template_file.name.replace('.template.json', '')
        templates.append((template_file, key))
    return templates


def main():
    parser = argparse.ArgumentParser(
        description='Hydrate all workflow templates for a specific environment'
    )
    parser.add_argument(
        '-e', '--env',
        required=True,
        help=f'Environment name ({", ".join(list_available_environments())})'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show verbose output from each hydration'
    )
    args = parser.parse_args()

    # Load and validate environment config
    try:
        env_config = load_env_config(args.env)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading environment config: {e}")
        sys.exit(1)

    base_dir = Path(__file__).parent.parent.parent
    workflows_dir = base_dir / 'n8n' / 'workflows'
    output_dir = base_dir / 'n8n' / 'workflows' / 'generated' / args.env

    # Discover templates
    templates = discover_templates(workflows_dir)

    if not templates:
        print(f"No *.template.json files found in {workflows_dir}")
        sys.exit(1)

    print("=" * 70)
    print(f"Hydrating All Workflows for [{env_config['displayName']}]")
    print("=" * 70)
    print()

    print_config_summary(env_config)
    print()

    print(f"Output directory: {output_dir}")
    print(f"Templates discovered: {len(templates)}")
    print()

    # Hydrate each template
    success_count = 0
    failed_templates = []

    for template_path, workflow_key in templates:
        print(f"Hydrating [{workflow_key}]...")

        try:
            hydrate_workflow(
                template_path=template_path,
                workflow_key=workflow_key,
                env_config=env_config,
                base_dir=base_dir,
                output_dir=output_dir
            )
            print(f"  Done")
            success_count += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            failed_templates.append((workflow_key, str(e)))

        print()

    # Summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"  Total: {len(templates)}")
    print(f"  Success: {success_count}")
    print(f"  Failed: {len(failed_templates)}")

    if failed_templates:
        print()
        print("Failed workflows:")
        for key, error in failed_templates:
            print(f"  - {key}: {error}")
        sys.exit(1)
    else:
        print()
        print(f"All workflows hydrated for [{env_config['displayName']}]!")
        print(f"   Generated files are in: {output_dir}")


if __name__ == "__main__":
    main()
