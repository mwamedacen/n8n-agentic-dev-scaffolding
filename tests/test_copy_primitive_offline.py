"""Offline tests for helpers/copy_primitive.py."""
import subprocess
import sys
from pathlib import Path

import pytest

from helpers.copy_primitive import _list_available, _copy


_HARNESS = Path(__file__).parent.parent
_HELPER = _HARNESS / "helpers" / "copy_primitive.py"


def test_list_available_returns_shipped_primitives():
    """All four shipped primitives appear in the list; the `_minimal` scaffold seed does not."""
    available = _list_available()
    assert "lock_acquisition" in available
    assert "lock_release" in available
    assert "error_handler_lock_cleanup" in available
    assert "rate_limit_check" in available
    # Underscore-prefixed seeds are filtered out.
    assert not any(name.startswith("_") for name in available), available


def test_copy_creates_dest_when_missing(tmp_path):
    ws = tmp_path / "ws"
    (ws / "n8n-workflows-template").mkdir(parents=True)
    dst = _copy(ws, "rate_limit_check", force_overwrite=False)
    assert dst.exists()
    assert dst.read_text() == (_HARNESS / "primitives" / "workflows" / "rate_limit_check.template.json").read_text()


def test_copy_skips_when_dest_exists_without_force(tmp_path, capsys):
    ws = tmp_path / "ws"
    (ws / "n8n-workflows-template").mkdir(parents=True)
    dst = ws / "n8n-workflows-template" / "rate_limit_check.template.json"
    dst.write_text("placeholder")
    _copy(ws, "rate_limit_check", force_overwrite=False)
    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "--force-overwrite" in out
    assert dst.read_text() == "placeholder"  # unchanged


def test_copy_overwrites_with_force(tmp_path):
    ws = tmp_path / "ws"
    (ws / "n8n-workflows-template").mkdir(parents=True)
    dst = ws / "n8n-workflows-template" / "rate_limit_check.template.json"
    dst.write_text("placeholder")
    _copy(ws, "rate_limit_check", force_overwrite=True)
    assert dst.read_text() != "placeholder"
    assert dst.read_text() == (_HARNESS / "primitives" / "workflows" / "rate_limit_check.template.json").read_text()


def test_copy_unknown_primitive_raises(tmp_path):
    ws = tmp_path / "ws"
    (ws / "n8n-workflows-template").mkdir(parents=True)
    with pytest.raises(SystemExit) as excinfo:
        _copy(ws, "definitely_not_a_primitive", force_overwrite=False)
    assert "not found" in str(excinfo.value)
    assert "Available:" in str(excinfo.value)


def test_cli_list_exits_zero(tmp_path):
    r = subprocess.run(
        [sys.executable, str(_HELPER), "--workspace", str(tmp_path), "--list"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "rate_limit_check" in r.stdout


def test_cli_no_name_lists_and_exits_two(tmp_path):
    """No --name and no --list prints the available list and exits non-zero so scripts can detect it."""
    r = subprocess.run(
        [sys.executable, str(_HELPER), "--workspace", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert "rate_limit_check" in r.stdout


def test_cli_lock_primitive_prints_registration_note(tmp_path):
    ws = tmp_path / "ws"
    (ws / "n8n-workflows-template").mkdir(parents=True)
    r = subprocess.run(
        [sys.executable, str(_HELPER), "--workspace", str(ws), "--name", "lock_acquisition"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "create_lock.py" in r.stdout, r.stdout
