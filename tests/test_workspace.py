"""Tests for helpers/workspace.py — no real n8n needed."""
import pytest
from pathlib import Path
from unittest.mock import patch


def test_workspace_root_default(tmp_path):
    with patch("os.getcwd", return_value=str(tmp_path)):
        from helpers.workspace import workspace_root
        result = workspace_root()
    assert result == tmp_path / "n8n-harness-workspace"


def test_workspace_root_override(tmp_path):
    from helpers.workspace import workspace_root
    custom = tmp_path / "custom-ws"
    result = workspace_root(str(custom))
    assert result == custom.resolve()


def test_harness_root_contains_helpers():
    from helpers.workspace import harness_root
    root = harness_root()
    assert (root / "helpers").is_dir()


def test_ensure_workspace_ok(tmp_path):
    ws = tmp_path / "ws"
    (ws / "n8n-config").mkdir(parents=True)
    (ws / "n8n-workflows-template").mkdir(parents=True)
    from helpers.workspace import ensure_workspace
    ensure_workspace(ws)  # must not raise


def test_ensure_workspace_missing(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    from helpers.workspace import ensure_workspace
    with pytest.raises(SystemExit):
        ensure_workspace(ws)


def test_assert_not_in_harness_outside(tmp_path):
    from helpers.workspace import assert_not_in_harness
    assert_not_in_harness(tmp_path / "some-file.json")  # must not raise


def test_assert_not_in_harness_inside():
    from helpers.workspace import assert_not_in_harness, harness_root
    inside = harness_root() / "helpers" / "output.json"
    with pytest.raises(RuntimeError, match="harness"):
        assert_not_in_harness(inside)
