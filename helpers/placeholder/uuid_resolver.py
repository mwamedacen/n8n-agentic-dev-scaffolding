"""Resolve {{INTERPOLATE:uuid:identifier}} (alias `{{@:uuid:identifier}}`) placeholders with fresh UUIDs."""
import re
import uuid

PATTERN = re.compile(r"\{\{(?:INTERPOLATE|@):uuid:([^}]+)\}\}")


def resolve(text: str) -> str:
    """Replace each {{INTERPOLATE:uuid:identifier}} / {{@:uuid:identifier}} with a fresh UUID v4.

    Each unique identifier gets one consistent UUID within a single resolve call.
    Different identifiers always get different UUIDs.
    """
    seen: dict[str, str] = {}

    def _replace(match: re.Match) -> str:
        identifier = match.group(1).strip()
        if identifier not in seen:
            seen[identifier] = str(uuid.uuid4())
        return seen[identifier]

    return PATTERN.sub(_replace, text)
