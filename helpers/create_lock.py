#!/usr/bin/env python3
"""Copy lock primitive templates from harness/primitives into the workspace and register them."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from helpers.workspace import workspace_root, harness_root


_PRIMITIVES = {
    "lock_acquisition": "Lock Acquisition",
    "lock_release": "Lock Release",
}
_ERROR_HANDLER = ("error_handler_lock_cleanup", "Error Handler Lock Cleanup")


def _copy_primitive(workspace: Path, key: str) -> Path:
    src = harness_root() / "primitives" / "workflows" / f"{key}.template.json"
    if not src.exists():
        raise FileNotFoundError(f"Primitive missing: {src}")
    dst_dir = workspace / "n8n-workflows-template"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"{key}.template.json"
    if dst.exists():
        print(f"  Already in workspace: {dst} (skipping copy)")
    else:
        shutil.copyfile(src, dst)
        print(f"  Copied {src.name} → {dst}")
    return dst


def _register_via_create_workflow(workspace: Path, key: str, name: str, tier: str) -> None:
    """Register the workflow in env YAMLs (and mint placeholder IDs) without re-writing the template."""
    cmd = [
        sys.executable,
        str(Path(__file__).parent / "create_workflow.py"),
        "--workspace", str(workspace),
        "--key", key,
        "--name", name,
        "--no-template",
        "--tier", tier,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, file=sys.stderr)
        print(r.stderr, file=sys.stderr)
        raise SystemExit(r.returncode)
    print(r.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--include-error-handler", action="store_true", dest="include_error_handler")
    args = parser.parse_args()

    ws = workspace_root(args.workspace)

    primitives = dict(_PRIMITIVES)
    if args.include_error_handler:
        key, name = _ERROR_HANDLER
        primitives[key] = name

    for key, name in primitives.items():
        _copy_primitive(ws, key)
        _register_via_create_workflow(ws, key, name, "Tier 0a: leaves")

    print("create-lock complete.")


if __name__ == "__main__":
    main()
