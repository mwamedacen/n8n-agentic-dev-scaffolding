"""Post-hydration validation: check for residual placeholders.

Catches all three placeholder forms (`HYDRATE`, `INTERPOLATE`, `@`) so partial
migrations from the old `HYDRATE` syntax fail loudly. Resolvers only substitute
`INTERPOLATE` / `@` — any leftover `HYDRATE` form means the template still uses
the old syntax and should be migrated via `helpers/migrate_syntax.py`.
"""
import re
from pathlib import Path

RESIDUAL_PATTERN = re.compile(r"\{\{(?:HYDRATE|INTERPOLATE|@):[^}]+\}\}")


def check_residuals(text: str) -> list[str]:
    """Return list of all residual placeholder tokens found in text."""
    return RESIDUAL_PATTERN.findall(text)


def validate(text: str, source_label: str = "") -> None:
    """Raise ValueError if any residual placeholders remain after hydration."""
    residuals = check_residuals(text)
    if residuals:
        label = f" in {source_label}" if source_label else ""
        raise ValueError(
            f"Residual placeholders found{label}: {', '.join(residuals)}\n"
            "Check that all placeholder paths resolve correctly."
        )


def validate_no_absolute_paths(text: str) -> None:
    """Raise ValueError if any placeholder contains an absolute path."""
    absolutes = re.findall(r"\{\{(?:HYDRATE|INTERPOLATE|@):\w+:(/[^}]+)\}\}", text)
    if absolutes:
        raise ValueError(
            f"Absolute paths are forbidden in placeholders: {', '.join(absolutes)}"
        )
