"""Offline tests for init.py and doctor.py — no real n8n needed."""
import subprocess
import sys
from pathlib import Path


def _harness() -> Path:
    return Path(__file__).parent.parent


def run(*args, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


class TestInit:
    def test_creates_workspace(self, tmp_path):
        ws = tmp_path / "ws"
        r = run(str(_harness() / "helpers" / "init.py"), "--workspace", str(ws))
        assert r.returncode == 0, r.stderr
        assert (ws / "n8n-config").is_dir()
        assert (ws / "n8n-workflows-template").is_dir()
        assert (ws / "N8N-HARNESS-MEMORY.md").is_file()
        assert (ws / "n8n-config" / ".env.example").is_file()

    def test_idempotent_refusal(self, tmp_path):
        ws = tmp_path / "ws"
        run(str(_harness() / "helpers" / "init.py"), "--workspace", str(ws))
        r = run(str(_harness() / "helpers" / "init.py"), "--workspace", str(ws))
        combined = r.stdout + r.stderr
        assert "already exists" in combined.lower()
        assert r.returncode == 1

    def test_force_recreates(self, tmp_path):
        ws = tmp_path / "ws"
        run(str(_harness() / "helpers" / "init.py"), "--workspace", str(ws))
        sentinel = ws / "sentinel.txt"
        sentinel.write_text("hello")
        r = run(str(_harness() / "helpers" / "init.py"), "--workspace", str(ws), "--force")
        assert r.returncode == 0
        assert not sentinel.exists()


class TestDoctor:
    def test_no_workspace(self, tmp_path):
        r = run(
            str(_harness() / "helpers" / "doctor.py"),
            "--workspace", str(tmp_path / "nonexistent"),
        )
        assert "doctor report" in r.stdout.lower()
        # Should not crash with an unhandled traceback
        assert "Traceback" not in r.stderr

    def test_empty_workspace_reports_fail(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        r = run(str(_harness() / "helpers" / "doctor.py"), "--workspace", str(ws))
        assert "doctor report" in r.stdout.lower()
        assert r.returncode == 1

    def test_no_env_configured(self, tmp_path):
        ws = tmp_path / "ws"
        (ws / "n8n-config").mkdir(parents=True)
        (ws / "n8n-workflows-template").mkdir(parents=True)
        r = run(str(_harness() / "helpers" / "doctor.py"), "--workspace", str(ws))
        output = r.stdout
        assert "no env" in output.lower() or "warn" in output.lower()
        assert r.returncode == 0  # WARN rows don't cause non-zero exit
