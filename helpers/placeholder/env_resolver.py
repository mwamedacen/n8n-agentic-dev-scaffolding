"""Resolve {{HYDRATE:env:key.path}} placeholders against loaded YAML config."""
import re
from pathlib import Path
from typing import Any

from helpers.config import get_config_value, load_yaml, load_env

PATTERN = re.compile(r"\{\{HYDRATE:env:([^}]+)\}\}")


def resolve(text: str, env_name: str, workspace: Path) -> str:
    """Replace all {{HYDRATE:env:...}} tokens in text with config values."""
    data = load_yaml(env_name, workspace)
    load_env(env_name, workspace)

    def _replace(match: re.Match) -> str:
        dot_path = match.group(1)
        try:
            val = get_config_value(data, dot_path)
        except KeyError:
            raise ValueError(f"Placeholder {{{{HYDRATE:env:{dot_path}}}}} not found in {env_name}.yml")
        return str(val)

    return PATTERN.sub(_replace, text)
