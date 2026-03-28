#!/usr/bin/env python3
"""
Environment configuration loader for multi-environment n8n workflow support.

Loads YAML configuration files from n8n/environments/ and provides utilities
for accessing nested configuration values using dot notation.

Usage:
    from env_config import load_env_config, get_config_value

    config = load_env_config('dev')
    drive_id = get_config_value(config, 'sharepoint.driveId')
    workflow_id = get_config_value(config, 'workflows.periodic_excel_report.id')
"""

import yaml
from pathlib import Path
from typing import Any, Dict, List


# Required top-level keys that must be present in every environment config
REQUIRED_KEYS = [
    'name',
    'displayName',
    'n8n.instanceName',
]


def get_environments_dir() -> Path:
    """Get the path to the environments directory."""
    return Path(__file__).parent.parent / 'environments'


def list_available_environments() -> List[str]:
    """List all available environment names."""
    env_dir = get_environments_dir()
    if not env_dir.exists():
        return []
    return sorted([f.stem for f in env_dir.glob('*.yaml')])


def load_env_config(env_name: str) -> Dict[str, Any]:
    """
    Load environment configuration from YAML file.

    Args:
        env_name: Environment name (e.g., 'dev', 'staging', 'prod')

    Returns:
        Dictionary containing all environment configuration

    Raises:
        FileNotFoundError: If environment config file doesn't exist
        ValueError: If configuration is missing required keys
    """
    env_dir = get_environments_dir()
    config_path = env_dir / f'{env_name}.yaml'

    if not config_path.exists():
        available = list_available_environments()
        raise FileNotFoundError(
            f"Environment config not found: {config_path}\n"
            f"Available environments: {', '.join(available) if available else 'none'}"
        )

    with open(config_path, 'r') as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Environment '{env_name}' has invalid YAML:\n  {e}")

    if not isinstance(config, dict):
        raise ValueError(
            f"Environment '{env_name}' config is empty or not a valid YAML mapping"
        )

    missing_keys = validate_config(config)
    if missing_keys:
        raise ValueError(
            f"Environment '{env_name}' is missing required keys:\n"
            f"  - {chr(10) + '  - '.join(missing_keys)}"
        )

    return config


def get_config_value(config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """
    Get a value from config using dot notation.

    Args:
        config: Configuration dictionary
        key_path: Dot-separated path (e.g., 'sharepoint.driveId')
        default: Default value if key not found

    Returns:
        Value at the specified path, or default if not found
    """
    keys = key_path.split('.')
    value = config

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


def flatten_config(config: Dict[str, Any], prefix: str = '') -> Dict[str, Any]:
    """
    Flatten a nested config dictionary into dot-notation keys.

    Args:
        config: Nested configuration dictionary
        prefix: Current key prefix (used in recursion)

    Returns:
        Flat dictionary with dot-notation keys

    Example:
        {'sharepoint': {'driveId': 'abc'}}
        becomes
        {'sharepoint.driveId': 'abc'}
    """
    result = {}

    for key, value in config.items():
        full_key = f'{prefix}.{key}' if prefix else key

        if isinstance(value, dict):
            result.update(flatten_config(value, full_key))
        else:
            result[full_key] = value

    return result


def validate_config(config: Dict[str, Any]) -> List[str]:
    """
    Validate that all required keys are present in the config.

    Validates:
    1. Required structural keys (name, displayName, n8n.instanceName)
    2. Every workflow entry has both 'id' and 'name' sub-keys

    Args:
        config: Configuration dictionary to validate

    Returns:
        List of missing key paths (empty if all required keys present)
    """
    missing = []

    # Check required structural keys
    for key in REQUIRED_KEYS:
        if get_config_value(config, key) is None:
            missing.append(key)

    # Dynamic workflow validation - check ALL workflows have id + name
    workflows = config.get('workflows', {})
    if not workflows:
        missing.append('workflows (at least one workflow required)')
    else:
        for wf_key, wf_val in workflows.items():
            if not isinstance(wf_val, dict):
                missing.append(f'workflows.{wf_key} (must be a dict with id and name)')
            else:
                if not wf_val.get('id'):
                    missing.append(f'workflows.{wf_key}.id')
                if not wf_val.get('name'):
                    missing.append(f'workflows.{wf_key}.name')

    return missing


def get_workflow_name_with_postfix(config: Dict[str, Any], base_name: str) -> str:
    """
    Get a workflow name with the environment's postfix appended.

    Args:
        config: Environment configuration
        base_name: Base workflow name (without postfix)

    Returns:
        Workflow name with environment postfix (e.g., "My Workflow [DEV]")
    """
    postfix = config.get('workflowNamePostfix', '')
    return f"{base_name}{postfix}"


def print_config_summary(config: Dict[str, Any]) -> None:
    """Print a summary of the loaded configuration."""
    print(f"\nEnvironment Configuration Summary")
    print("=" * 50)
    print(f"  Name: {config.get('name')}")
    print(f"  Display Name: {config.get('displayName')}")
    print(f"  Postfix: '{config.get('workflowNamePostfix', '')}'")
    print(f"  n8n Instance: {get_config_value(config, 'n8n.instanceName')}")

    # Print credentials if present
    credentials = config.get('credentials', {})
    if credentials:
        print(f"  Credentials: {', '.join(credentials.keys())}")

    workflows = config.get('workflows', {})
    print(f"  Workflows configured: {len(workflows)}")
    for key in sorted(workflows.keys()):
        print(f"    - {key}: {workflows[key].get('name', 'unnamed')}")
    print("=" * 50)


# CLI for testing
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python env_config.py <env_name>")
        print(f"Available environments: {', '.join(list_available_environments())}")
        sys.exit(1)

    env_name = sys.argv[1]

    try:
        config = load_env_config(env_name)
        print_config_summary(config)

        if '--verbose' in sys.argv:
            print("\nAll configuration keys:")
            for key, value in sorted(flatten_config(config).items()):
                str_value = str(value)
                if len(str_value) > 50:
                    str_value = str_value[:47] + '...'
                print(f"  {key}: {str_value}")

    except (FileNotFoundError, ValueError, yaml.YAMLError) as e:
        print(f"Error: {e}")
        sys.exit(1)
