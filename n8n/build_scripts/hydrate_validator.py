"""Validate that generated workflows have no unresolved placeholders."""

import re
import json
from pathlib import Path
from typing import Dict, Any


# Patterns to detect unresolved placeholders
PLACEHOLDER_PATTERNS = [
    (r'\{\{HYDRATE:[^}]+\}\}', 'HYDRATE'),
]


def validate_no_placeholders(workflow_path: Path, workflow: Dict[str, Any]) -> None:
    """
    Validate that no HYDRATE placeholders remain in the workflow.

    Args:
        workflow_path: Path to the generated workflow file
        workflow: The workflow dict that was saved

    Raises:
        ValueError: If any placeholders are found
    """
    workflow_str = json.dumps(workflow)

    found_issues = []
    for pattern, name in PLACEHOLDER_PATTERNS:
        matches = re.findall(pattern, workflow_str)
        if matches:
            found_issues.append((name, matches))

    if found_issues:
        error_lines = [f"Unresolved placeholders found in {workflow_path.name}:"]
        for name, matches in found_issues:
            unique_matches = sorted(set(matches))
            error_lines.append(f"  {name}: {len(matches)} occurrence(s)")
            for m in unique_matches[:5]:
                error_lines.append(f"    - {m}")
            if len(unique_matches) > 5:
                error_lines.append(f"    ... and {len(unique_matches) - 5} more")
        raise ValueError("\n".join(error_lines))

    print(f"  Validated: no unresolved placeholders")
