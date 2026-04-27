"""Resolve {{HYDRATE:py:path}} placeholders; emit DEHYDRATE markers for round-trip."""
import json
import re
from pathlib import Path

PATTERN = re.compile(r"\{\{HYDRATE:py:([^}]+)\}\}")
DEHYDRATE_OPEN = "# DEHYDRATE:py:{path}"
DEHYDRATE_CLOSE = "# /DEHYDRATE:py:{path}"
DEHYDRATE_PATTERN = re.compile(
    r"# DEHYDRATE:py:([^\n]+)\n(.+?)\n# /DEHYDRATE:py:\1",
    re.DOTALL,
)

_MARKER_OPEN_PREFIX = "# DEHYDRATE:py:"
_MARKER_CLOSE_PREFIX = "# /DEHYDRATE:py:"


def resolve(text: str, workspace: Path) -> str:
    """Replace {{HYDRATE:py:path}} with JSON-escaped Python content wrapped in line-comment markers."""

    def _replace(match: re.Match) -> str:
        rel_path = match.group(1).strip()
        if rel_path.startswith("/"):
            raise ValueError(
                f"Absolute paths in placeholders are forbidden: {{{{HYDRATE:py:{rel_path}}}}}"
            )
        full = workspace / rel_path
        if not full.exists():
            raise FileNotFoundError(f"Python file not found: {full}")
        content = full.read_text(encoding="utf-8")
        if _MARKER_OPEN_PREFIX in content or _MARKER_CLOSE_PREFIX in content:
            raise ValueError(
                f"Python file {rel_path} contains a DEHYDRATE marker substring; "
                "this would corrupt round-trip dehydration. Remove the marker from the source."
            )
        block = (
            DEHYDRATE_OPEN.format(path=rel_path) + "\n"
            + content.rstrip("\n") + "\n"
            + DEHYDRATE_CLOSE.format(path=rel_path)
        )
        return json.dumps(block)[1:-1]

    return PATTERN.sub(_replace, text)


def _walk_strings(obj, fn):
    if isinstance(obj, dict):
        return {k: _walk_strings(v, fn) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_strings(v, fn) for v in obj]
    if isinstance(obj, str):
        return fn(obj)
    return obj


def dehydrate(text: str) -> str:
    """Collapse DEHYDRATE-wrapped Python blocks back to {{HYDRATE:py:...}} placeholders. JSON-aware."""
    data = json.loads(text)
    data = _walk_strings(
        data,
        lambda s: DEHYDRATE_PATTERN.sub(
            lambda m: "{{HYDRATE:py:" + m.group(1).strip() + "}}", s
        ),
    )
    return json.dumps(data, indent=2)
