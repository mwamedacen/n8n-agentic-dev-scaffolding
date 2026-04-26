#!/usr/bin/env python3
"""
Bootstrap placeholder workflows in n8n for a new environment.

Creates minimal empty workflows in n8n via the API and updates the
environment YAML config with the newly assigned workflow IDs.

Usage:
    python3 bootstrap_workflows.py dev
    python3 bootstrap_workflows.py prod --dry-run
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path


def load_env_file(env_file: Path) -> dict:
    """Load a .env file and return key-value pairs."""
    env_vars = {}
    if not env_file.exists():
        return env_vars

    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                env_vars[key] = value

    return env_vars


def load_yaml_config(config_path: Path) -> dict:
    """Load YAML config file."""
    import yaml
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_api_base(config: dict) -> str:
    """Determine API base URL from n8n.instanceName."""
    instance = config.get('n8n', {}).get('instanceName', '')
    if instance.startswith('http://') or instance.startswith('https://'):
        return instance.rstrip('/')
    elif 'localhost' in instance or '127.0.0.1' in instance:
        return f'http://{instance.rstrip("/")}'
    else:
        return f'https://{instance.rstrip("/")}'


def create_workflow(api_base: str, api_key: str, name: str, dry_run: bool = False) -> dict:
    """
    Create a minimal placeholder workflow in n8n.

    Returns:
        Dict with 'id' and 'name' from the n8n API response
    """
    payload = {
        "name": name,
        "nodes": [],
        "connections": {},
        "settings": {}
    }

    if dry_run:
        print(f"  [DRY RUN] Would create workflow: {name}")
        return {"id": "DRY_RUN_ID", "name": name}

    url = f"{api_base}/api/v1/workflows"
    data = json.dumps(payload).encode('utf-8')

    req = urllib.request.Request(
        url,
        data=data,
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'X-N8N-API-KEY': api_key
        }
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        raise RuntimeError(
            f"Failed to create workflow '{name}': HTTP {e.code}\n{error_body}"
        )


def update_yaml_workflow_id(config_path: Path, workflow_key: str, new_id: str) -> None:
    """
    Update the workflow ID in the YAML config file using regex replacement.

    Looks for the pattern:
        workflow_key:
          id: <old_value>

    And replaces the id value with the new one.
    """
    with open(config_path, 'r') as f:
        content = f.read()

    # Pattern matches the workflow key block and replaces the id value
    # Handles: "id: 123", "id: ''", "id: \"\"", "id: null", "id: "
    pattern = re.compile(
        rf'(  {re.escape(workflow_key)}:\s*\n\s*id:\s*)([^\n]*)',
        re.MULTILINE
    )

    match = pattern.search(content)
    if not match:
        print(f"  Warning: Could not find {workflow_key}.id in {config_path}")
        return

    new_content = pattern.sub(rf"\g<1>'{new_id}'", content)

    with open(config_path, 'w') as f:
        f.write(new_content)


def bootstrap_env(env_name: str, dry_run: bool = False) -> int:
    """Bootstrap placeholder workflows for `env_name`. Importable + CLI entry.

    Returns exit code (0 ok, 1 fail). Stays compatible with the old CLI shape:
    prints a banner + per-workflow lines + a summary block to stdout.
    """
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent.parent
    config_path = project_dir / 'n8n' / 'environments' / f'{env_name}.yaml'
    if not config_path.exists():
        # Phase 3: also accept attached.<env_name>.yaml
        alt = project_dir / 'n8n' / 'environments' / f'attached.{env_name}.yaml'
        if alt.exists():
            config_path = alt
    root_env_file = project_dir / '.env'
    env_file = project_dir / f'.env.{env_name}'

    if not config_path.exists():
        print(f"Error: Environment config not found: {config_path}")
        env_dir = project_dir / 'n8n' / 'environments'
        if env_dir.exists():
            available = [f.stem for f in env_dir.glob('*.yaml')]
            if available:
                print(f"Available environments: {', '.join(sorted(available))}")
        return 1

    # Load config + layered secrets:
    #   1. root .env loads first (defaults)
    #   2. .env.<env> overlays on top — env-specific values WIN.
    config = load_yaml_config(config_path)
    layered_env = {}
    layered_env.update(load_env_file(root_env_file))
    layered_env.update(load_env_file(env_file))
    for key, value in layered_env.items():
        os.environ[key] = value

    # Resolve instance: env var wins, YAML fallback.
    instance = os.environ.get('N8N_INSTANCE_NAME', '').strip()
    if not instance:
        instance = config.get('n8n', {}).get('instanceName', '')
    if instance.startswith(('http://', 'https://')):
        api_base = instance.rstrip('/')
    elif 'localhost' in instance or '127.0.0.1' in instance:
        api_base = f'http://{instance.rstrip("/")}'
    else:
        api_base = f'https://{instance.rstrip("/")}'

    api_key = os.environ.get('N8N_API_KEY', '')
    if not api_key:
        print(f"Error: N8N_API_KEY not found in {root_env_file}, {env_file}, or environment.")
        return 1

    display_name = config.get('displayName', env_name)
    postfix = config.get('workflowNamePostfix', '')
    workflows = config.get('workflows', {})
    if not workflows:
        print("No workflows defined in the environment config.")
        return 1

    print("=" * 60)
    print(f"Bootstrapping Workflows for [{display_name}]")
    if dry_run:
        print("  ** DRY RUN MODE **")
    print("=" * 60)
    print(f"  API Base: {api_base}")
    print(f"  Workflows to create: {len(workflows)}")
    print()

    created = []
    failed = []

    for wf_key, wf_config in workflows.items():
        existing_id = wf_config.get('id', '')
        wf_name = wf_config.get('name', wf_key)
        full_name = f"{wf_name}{postfix}"

        existing_str = str(existing_id).strip()
        is_placeholder = (
            not existing_str
            or existing_str in ('null', "''", '""', 'placeholder')
            or existing_str.startswith('your-')
        )
        if not is_placeholder:
            print(f"  [{wf_key}] Already has ID: {existing_id} - skipping")
            continue

        try:
            result = create_workflow(api_base, api_key, full_name, dry_run=dry_run)
            new_id = str(result.get('id', ''))
            if not dry_run and new_id:
                update_yaml_workflow_id(config_path, wf_key, new_id)
            created.append((wf_key, full_name, new_id))
            print(f"  [{wf_key}] Created: {full_name} -> ID: {new_id}")
        except Exception as e:
            failed.append((wf_key, str(e)))
            print(f"  [{wf_key}] FAILED: {e}")

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Created: {len(created)}")
    print(f"  Failed:  {len(failed)}")
    print(f"  Skipped: {len(workflows) - len(created) - len(failed)}")

    if created and not dry_run:
        print()
        print("Next steps:")
        print(f"  1. Review updated config: {config_path}")
        print(f"  2. Deploy workflows: n8n-harness -c \"for k in <keys>: deploy(k)\" or ./deploy_all.sh {env_name}")
        print(f"  3. Verify in n8n UI: {api_base}")

    if failed:
        print()
        print("Failed workflows:")
        for wf_key, error in failed:
            print(f"  - {wf_key}: {error}")
        return 1

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Bootstrap placeholder workflows in n8n for a new environment'
    )
    parser.add_argument('environment', help='Environment name (e.g., dev, staging, prod)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be created')
    args = parser.parse_args()
    sys.exit(bootstrap_env(args.environment, dry_run=args.dry_run))


if __name__ == '__main__':
    main()
