#!/usr/bin/env python3
"""Scaffold an n8n-harness workspace.

Default location is ``${PWD}/n8n-harness-workspace``. If you run from inside an
existing workspace directory (basename ``n8n-harness-workspace``), the existing
workspace is used in place. Pass ``--workspace <path>`` to override.
"""
import argparse
import shutil
import sys
from pathlib import Path

# Make `from helpers.X import ...` work when script is invoked directly.
sys.path.insert(0, str(Path(__file__).parent.parent))

from helpers.workspace import workspace_root

_MEMORY = """\
# N8N-HARNESS-MEMORY

Persistent agent memory for this n8n-harness workspace.

## Skill router
- Refer to `<harness>/SKILL.md` to route any n8n-related request.

## Workspace
- Env configs: `n8n-config/` (YAML + .env.<env>)

## Notes
(add session-persistent notes here)
"""

_GITIGNORE = """\
n8n-build/
.env.*
"""


def _scaffold(ws: Path, force: bool) -> None:
    if ws.exists():
        if not force:
            print(f"Workspace already exists at {ws}. Use --force to recreate (DESTRUCTIVE).", file=sys.stderr)
            sys.exit(1)
        shutil.rmtree(ws)

    dirs = [
        ws / "n8n-config",
        ws / "n8n-workflows-template",
        ws / "n8n-build",
        ws / "n8n-prompts" / "prompts",
        ws / "n8n-prompts" / "datasets",
        ws / "n8n-prompts" / "evals",
        ws / "n8n-functions" / "js",
        ws / "n8n-functions" / "py",
        ws / "n8n-functions-tests",
        ws / "n8n-assets" / "email-templates",
        ws / "n8n-assets" / "images",
        ws / "n8n-assets" / "misc",
        ws / "cloud-functions" / "functions",
        ws / "cloud-functions-tests",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    (ws / "N8N-HARNESS-MEMORY.md").write_text(_MEMORY)
    (ws / ".gitignore").write_text(_GITIGNORE)
    (ws / "n8n-config" / ".env.example").write_text(
        "# Document secret env-var names here (no values).\n"
        "# Copy relevant entries into .env.<env> with real values.\n"
    )

    print(f"Workspace created at {ws}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=None, help="Workspace path. Default: ${PWD}/n8n-harness-workspace, or ${PWD} if its basename is already n8n-harness-workspace.")
    parser.add_argument("--force", action="store_true", help="Recreate workspace if it already exists (DESTRUCTIVE)")
    args = parser.parse_args()
    _scaffold(workspace_root(args.workspace), args.force)


if __name__ == "__main__":
    main()
