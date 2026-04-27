"""Resolve {{HYDRATE:js:path}} placeholders; emit DEHYDRATE markers for round-trip."""
import json
import re
from pathlib import Path

PATTERN = re.compile(r"\{\{HYDRATE:js:([^}]+)\}\}")
DEHYDRATE_OPEN = "/* DEHYDRATE:js:{path} */"
DEHYDRATE_CLOSE = "/* /DEHYDRATE:js:{path} */"
DEHYDRATE_PATTERN = re.compile(
    r"/\* DEHYDRATE:js:([^*]+) \*/(.+?)/\* /DEHYDRATE:js:\1 \*/",
    re.DOTALL,
)


def resolve(text: str, workspace: Path) -> str:
    """Replace {{HYDRATE:js:path}} with JSON-escaped file content wrapped in DEHYDRATE markers."""

    def _replace(match: re.Match) -> str:
        rel_path = match.group(1).strip()
        if rel_path.startswith("/"):
            raise ValueError(
                f"Absolute paths in placeholders are forbidden: {{{{HYDRATE:js:{rel_path}}}}}"
            )
        full = workspace / rel_path
        if not full.exists():
            raise FileNotFoundError(f"JS file not found: {full}")
        content = full.read_text(encoding="utf-8")
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
    """Collapse DEHYDRATE-wrapped JS blocks back to {{HYDRATE:js:...}} placeholders. JSON-aware."""
    data = json.loads(text)
    data = _walk_strings(
        data,
        lambda s: DEHYDRATE_PATTERN.sub(
            lambda m: "{{HYDRATE:js:" + m.group(1).strip() + "}}", s
        ),
    )
    return json.dumps(data, indent=2)
