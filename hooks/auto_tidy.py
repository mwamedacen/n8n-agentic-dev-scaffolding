#!/usr/bin/env python3
"""PostToolUse hook: auto-tidy workflow templates.

Reads stdin JSON from Claude Code's hook event, extracts the file path,
filters to *.template.json, invokes tidy_workflow.py --in-place.

No re-entry guard needed: tidy_workflow.py writes the file via Python
open(..., 'w'), which is not a Claude Code Write/Edit tool call and
thus does not retrigger this hook.
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    file_path = event.get("tool_input", {}).get("file_path", "")
    if not file_path.endswith(".template.json"):
        sys.exit(0)

    p = Path(file_path).resolve()
    # Convention: <ws>/n8n-workflows-template/<key>.template.json
    ws = p.parent.parent
    key = p.stem.removesuffix(".template")

    # Guard: derived workspace must contain the expected subdirectory
    if not (ws / "n8n-workflows-template").is_dir():
        print(
            f"[auto_tidy] skipping: derived workspace {ws} has no n8n-workflows-template/ "
            f"(file_path does not match <ws>/n8n-workflows-template/<key>.template.json convention)",
            file=sys.stderr,
        )
        sys.exit(0)

    # Fall back to script-relative root so skill-mode (no CLAUDE_PLUGIN_ROOT) works too
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(Path(__file__).resolve().parent.parent)
    helper = Path(plugin_root) / "helpers" / "tidy_workflow.py"

    result = subprocess.run(
        ["python3", str(helper),
         "--workspace", str(ws),
         "--workflow-key", key,
         "--in-place"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"[auto_tidy] tidy_workflow.py exited {result.returncode}: {result.stderr}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
