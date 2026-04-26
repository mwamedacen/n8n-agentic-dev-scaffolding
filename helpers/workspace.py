from pathlib import Path


def workspace_root(override=None) -> Path:
    """Return workspace root: ${PWD}/n8n-harness-workspace, or override."""
    if override:
        return Path(override).resolve()
    return Path.cwd() / "n8n-harness-workspace"


def harness_root() -> Path:
    """Return the harness package root (parent of helpers/)."""
    return Path(__file__).parent.parent.resolve()


def ensure_workspace(path: Path) -> None:
    """Assert required workspace subdirs exist; raise SystemExit with actionable message otherwise."""
    required = [
        path / "n8n-config",
        path / "n8n-workflows-template",
    ]
    missing = [str(d) for d in required if not d.is_dir()]
    if missing:
        raise SystemExit(
            f"Workspace at {path} is incomplete or missing.\n"
            f"Missing: {', '.join(missing)}\n"
            "Run `python3 <harness>/helpers/init.py` first."
        )


def assert_not_in_harness(out_path: Path) -> None:
    """Raise RuntimeError if out_path would land inside the harness directory."""
    harness = harness_root()
    try:
        Path(out_path).resolve().relative_to(harness)
        raise RuntimeError(
            f"Refusing to write inside the harness directory: {out_path}\n"
            "Helpers must only write to workspace paths."
        )
    except ValueError:
        pass  # Not inside harness — good
