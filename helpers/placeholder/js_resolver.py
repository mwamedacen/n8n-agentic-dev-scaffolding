"""Resolve {{HYDRATE:js:path}} placeholders; emit DEHYDRATE markers for round-trip."""
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
    """Replace {{HYDRATE:js:path}} with file content wrapped in DEHYDRATE markers."""

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
        open_marker = DEHYDRATE_OPEN.format(path=rel_path)
        close_marker = DEHYDRATE_CLOSE.format(path=rel_path)
        return f"{open_marker}\n{content}\n{close_marker}"

    return PATTERN.sub(_replace, text)


def dehydrate(text: str) -> str:
    """Replace DEHYDRATE-wrapped JS blocks back to {{HYDRATE:js:...}} placeholders."""

    def _replace(match: re.Match) -> str:
        rel_path = match.group(1).strip()
        return f"{{{{HYDRATE:js:{rel_path}}}}}"

    return DEHYDRATE_PATTERN.sub(_replace, text)
