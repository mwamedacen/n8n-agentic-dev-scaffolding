"""Tests for helpers/init.py _scaffold output (separate from workspace-resolution tests)."""
from pathlib import Path
from unittest.mock import patch


def _run_scaffold(tmp_path):
    """Run _scaffold with tmp_path as cwd so default workspace resolves correctly."""
    with patch("os.getcwd", return_value=str(tmp_path)):
        from helpers.init import _scaffold
        ws = tmp_path / "n8n-evol-I-workspace"
        _scaffold(ws, force=False)
    return ws, tmp_path


def test_agents_md_created(tmp_path):
    ws, _ = _run_scaffold(tmp_path)
    assert (ws / "AGENTS.md").exists()
    content = (ws / "AGENTS.md").read_text()
    assert "SKILL.md" in content
    assert "N8N-WORKSPACE-MEMORY.md" in content
    assert "Update" in content  # maintain-incentive paragraph present


def test_workspace_memory_created(tmp_path):
    ws, _ = _run_scaffold(tmp_path)
    assert (ws / "N8N-WORKSPACE-MEMORY.md").exists()
    content = (ws / "N8N-WORKSPACE-MEMORY.md").read_text()
    assert "Workflows" in content


def test_old_memory_file_not_created(tmp_path):
    ws, _ = _run_scaffold(tmp_path)
    assert not (ws / "N8N-HARNESS-MEMORY.md").exists()


def test_claude_md_alias_at_project_root(tmp_path):
    ws, project_root = _run_scaffold(tmp_path)
    claude = project_root / "CLAUDE.md"
    assert claude.exists()
    assert "AGENTS.md" in claude.read_text()


def test_copilot_alias_at_project_root(tmp_path):
    ws, project_root = _run_scaffold(tmp_path)
    copilot = project_root / ".github" / "copilot-instructions.md"
    assert copilot.exists()
    assert "AGENTS.md" in copilot.read_text()


def test_alias_not_overwritten_if_exists(tmp_path):
    existing_content = "existing CLAUDE.md content\n"
    (tmp_path / "CLAUDE.md").write_text(existing_content)
    _run_scaffold(tmp_path)
    assert (tmp_path / "CLAUDE.md").read_text() == existing_content


def test_alias_skipped_for_nondefault_workspace(tmp_path):
    custom_ws = tmp_path / "my-custom-ws"
    from helpers.init import _scaffold
    _scaffold(custom_ws, force=False)
    # Alias files must NOT be written when workspace is at non-default path
    assert not (tmp_path / "CLAUDE.md").exists()
    assert not (tmp_path / ".github" / "copilot-instructions.md").exists()
