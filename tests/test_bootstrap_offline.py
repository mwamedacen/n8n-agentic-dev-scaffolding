"""Offline tests for helpers/bootstrap_env.py — uses unittest.mock for HTTP."""
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml


def _harness() -> Path:
    return Path(__file__).parent.parent


def run(*args, env_extra=None) -> subprocess.CompletedProcess:
    import os
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        env=env,
    )


class TestBootstrapEnvFresh:
    """Tests for the fresh-env path (no YAML/env files exist)."""

    def test_fresh_creates_yaml_and_env(self, tmp_path):
        """Fresh bootstrap writes YAML and .env files."""
        ws = tmp_path / "ws"
        (ws / "n8n-config").mkdir(parents=True)
        (ws / "n8n-workflows-template").mkdir()

        # Mock the HTTP validation call
        with patch("helpers.n8n_client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"data": []}
            mock_get.return_value = mock_resp

            from helpers.bootstrap_env import main as bs_main
            import sys as _sys
            old_argv = _sys.argv
            _sys.argv = [
                "bootstrap_env.py",
                "--workspace", str(ws),
                "--env", "dev",
                "--instance", "localhost:8080",
                "--api-key", "fake-key",
                "--display-name", "Development",
                "--postfix", " [DEV]",
            ]
            try:
                bs_main()
            finally:
                _sys.argv = old_argv

        yaml_file = ws / "n8n-config" / "dev.yml"
        env_file = ws / "n8n-config" / ".env.dev"
        assert yaml_file.exists(), "YAML not written"
        assert env_file.exists(), ".env not written"

        data = yaml.safe_load(yaml_file.read_text())
        assert data["name"] == "dev"
        assert data["n8n"]["instanceName"] == "localhost:8080"
        assert "N8N_API_KEY=fake-key" in env_file.read_text()

    def test_validation_failure_rolls_back(self, tmp_path):
        """When live validation fails, stage-1 files are rolled back."""
        ws = tmp_path / "ws"
        (ws / "n8n-config").mkdir(parents=True)
        (ws / "n8n-workflows-template").mkdir()

        import requests
        with patch("helpers.n8n_client.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("refused")

            from helpers.bootstrap_env import main as bs_main
            import sys as _sys
            old_argv = _sys.argv
            _sys.argv = [
                "bootstrap_env.py",
                "--workspace", str(ws),
                "--env", "dev",
                "--instance", "localhost:8080",
                "--api-key", "fake-key",
            ]
            with pytest.raises(SystemExit) as exc:
                bs_main()
            assert exc.value.code == 1

        assert not (ws / "n8n-config" / "dev.yml").exists(), "YAML should be rolled back"
        assert not (ws / "n8n-config" / ".env.dev").exists(), ".env should be rolled back"

    def test_dry_run_writes_nothing(self, tmp_path):
        """--dry-run prints what would be done but creates no files."""
        ws = tmp_path / "ws"
        (ws / "n8n-config").mkdir(parents=True)
        (ws / "n8n-workflows-template").mkdir()

        r = run(
            str(_harness() / "helpers" / "bootstrap_env.py"),
            "--workspace", str(ws),
            "--env", "dev",
            "--instance", "localhost:8080",
            "--api-key", "fake-key",
            "--dry-run",
        )
        assert r.returncode == 0
        assert not (ws / "n8n-config" / "dev.yml").exists()
        assert not (ws / "n8n-config" / ".env.dev").exists()
        assert "dry-run" in r.stdout.lower()


class TestBootstrapEnvTopUp:
    """Tests for the top-up path (YAML exists, some IDs are placeholder)."""

    def _make_env(self, ws: Path, instance: str = "localhost:8080") -> None:
        """Create a pre-existing dev YAML + .env."""
        data = {
            "name": "dev",
            "displayName": "Development",
            "workflowNamePostfix": " [DEV]",
            "n8n": {"instanceName": instance},
            "credentials": {},
            "workflows": {},
        }
        (ws / "n8n-config" / "dev.yml").write_text(yaml.dump(data))
        (ws / "n8n-config" / ".env.dev").write_text("N8N_API_KEY=fake-key\n")

    def test_topup_mints_placeholder_ids(self, tmp_path):
        """Stage 3 mints IDs for placeholder workflows."""
        ws = tmp_path / "ws"
        (ws / "n8n-config").mkdir(parents=True)
        (ws / "n8n-workflows-template").mkdir()
        self._make_env(ws)

        # Add a placeholder workflow
        yaml_file = ws / "n8n-config" / "dev.yml"
        data = yaml.safe_load(yaml_file.read_text())
        data["workflows"] = {"foo": {"id": "", "name": "Foo"}}
        yaml_file.write_text(yaml.dump(data))

        with patch("helpers.n8n_client.requests.get") as mock_get, \
             patch("helpers.n8n_client.requests.post") as mock_post:
            mock_get.return_value.raise_for_status.return_value = None
            mock_get.return_value.json.return_value = {"data": []}
            mock_post.return_value.raise_for_status.return_value = None
            mock_post.return_value.json.return_value = {"id": "minted-id-123", "name": "Development Foo [DEV]"}

            from helpers.bootstrap_env import main as bs_main
            import sys as _sys
            old_argv = _sys.argv
            _sys.argv = [
                "bootstrap_env.py",
                "--workspace", str(ws),
                "--env", "dev",
                "--instance", "localhost:8080",
                "--api-key", "fake-key",
            ]
            try:
                bs_main()
            finally:
                _sys.argv = old_argv

        updated = yaml.safe_load(yaml_file.read_text())
        assert updated["workflows"]["foo"]["id"] == "minted-id-123"

    def test_topup_dry_run_shows_would_mint(self, tmp_path):
        """--dry-run in top-up mode prints what would be minted without POSTing."""
        ws = tmp_path / "ws"
        (ws / "n8n-config").mkdir(parents=True)
        (ws / "n8n-workflows-template").mkdir()
        self._make_env(ws)

        yaml_file = ws / "n8n-config" / "dev.yml"
        data = yaml.safe_load(yaml_file.read_text())
        data["workflows"] = {"foo": {"id": "", "name": "Foo"}}
        yaml_file.write_text(yaml.dump(data))

        r = run(
            str(_harness() / "helpers" / "bootstrap_env.py"),
            "--workspace", str(ws),
            "--env", "dev",
            "--dry-run",
            env_extra={"N8N_API_KEY": "fake-key"},
        )
        output = r.stdout + r.stderr
        assert "dry-run" in output.lower() or "would" in output.lower()

    def test_idempotent_noop(self, tmp_path):
        """Re-running bootstrap when YAML exists and all IDs are real is a no-op (exit 0)."""
        ws = tmp_path / "ws"
        (ws / "n8n-config").mkdir(parents=True)
        (ws / "n8n-workflows-template").mkdir()
        self._make_env(ws)

        yaml_file = ws / "n8n-config" / "dev.yml"
        data = yaml.safe_load(yaml_file.read_text())
        data["workflows"] = {"foo": {"id": "real-id-abc", "name": "Foo"}}
        yaml_file.write_text(yaml.dump(data))

        with patch("helpers.n8n_client.requests.get") as mock_get:
            mock_get.return_value.raise_for_status.return_value = None
            mock_get.return_value.json.return_value = {"data": []}

            from helpers import bootstrap_env
            import importlib
            importlib.reload(bootstrap_env)
            from helpers.bootstrap_env import main as bs_main
            import sys as _sys
            old_argv = _sys.argv
            _sys.argv = [
                "bootstrap_env.py",
                "--workspace", str(ws),
                "--env", "dev",
                "--instance", "localhost:8080",
                "--api-key", "fake-key",
            ]
            try:
                bs_main()  # Should not raise
            finally:
                _sys.argv = old_argv

        # YAML unchanged
        updated = yaml.safe_load(yaml_file.read_text())
        assert updated["workflows"]["foo"]["id"] == "real-id-abc"
