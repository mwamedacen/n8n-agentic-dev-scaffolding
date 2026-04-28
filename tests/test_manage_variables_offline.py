"""Offline tests for helpers/manage_variables.py — mocks N8nClient HTTP."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml


def _harness() -> Path:
    return Path(__file__).parent.parent


sys.path.insert(0, str(_harness()))


def _make_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "n8n-config").mkdir(parents=True)
    (ws / "n8n-workflows-template").mkdir(parents=True)
    (ws / "n8n-config" / "dev.yml").write_text(yaml.dump({
        "name": "dev",
        "displayName": "Development",
        "n8n": {"instanceName": "https://n8n.example.test"},
        "workflows": {},
    }))
    (ws / "n8n-config" / ".env.dev").write_text("N8N_API_KEY=fake\n")
    return ws


class TestList:
    def test_list_emits_all_variables(self, tmp_path, capsys):
        ws = _make_workspace(tmp_path)
        with patch("helpers.n8n_client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"data": [
                {"id": "v1", "key": "API_BASE", "value": "https://api.example.com"},
                {"id": "v2", "key": "DEBUG", "value": "true"},
            ]}
            mock_get.return_value = mock_resp

            import helpers.n8n_client as nc
            nc._CACHE.clear()
            import helpers.manage_variables as mv
            old_argv = sys.argv
            sys.argv = ["manage_variables.py", "--workspace", str(ws),
                        "list", "--env", "dev"]
            try:
                mv.main()
            finally:
                sys.argv = old_argv

        parsed = json.loads(capsys.readouterr().out)
        assert len(parsed) == 2
        assert {r["key"] for r in parsed} == {"API_BASE", "DEBUG"}

    def test_list_filter_by_name(self, tmp_path, capsys):
        ws = _make_workspace(tmp_path)
        with patch("helpers.n8n_client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"data": [
                {"id": "v1", "key": "API_BASE", "value": "x"},
                {"id": "v2", "key": "DEBUG", "value": "y"},
            ]}
            mock_get.return_value = mock_resp

            import helpers.n8n_client as nc
            nc._CACHE.clear()
            import helpers.manage_variables as mv
            old_argv = sys.argv
            sys.argv = ["manage_variables.py", "--workspace", str(ws),
                        "list", "--env", "dev", "--name", "DEBUG"]
            try:
                mv.main()
            finally:
                sys.argv = old_argv

        parsed = json.loads(capsys.readouterr().out)
        assert len(parsed) == 1
        assert parsed[0]["key"] == "DEBUG"


class TestCreate:
    def test_create_posts_with_key_field(self, tmp_path, capsys):
        ws = _make_workspace(tmp_path)
        with patch("helpers.n8n_client.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"id": "v-new", "key": "NEW_VAR", "value": "abc"}
            mock_post.return_value = mock_resp

            import helpers.n8n_client as nc
            nc._CACHE.clear()
            import helpers.manage_variables as mv
            old_argv = sys.argv
            sys.argv = ["manage_variables.py", "--workspace", str(ws),
                        "create", "--env", "dev",
                        "--name", "NEW_VAR", "--value", "abc"]
            try:
                mv.main()
            finally:
                sys.argv = old_argv

        body = mock_post.call_args_list[-1].kwargs.get("json")
        assert body == {"key": "NEW_VAR", "value": "abc"}

        captured = capsys.readouterr().out
        parsed = json.loads(captured.split("\n{")[0] if captured.startswith("[") else captured.split("Note:")[0])
        # The output is JSON followed by a Note line; just confirm the JSON parses and matches.
        first_block = captured.split("Note:")[0].strip()
        assert json.loads(first_block) == {"id": "v-new", "key": "NEW_VAR", "value": "abc"}
        assert "not version-controlled" in captured


class TestUpdate:
    def test_update_puts_to_variable_id(self, tmp_path, capsys):
        ws = _make_workspace(tmp_path)
        with patch("helpers.n8n_client.requests.put") as mock_put:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"id": "v1", "key": "EXISTING", "value": "new"}
            mock_put.return_value = mock_resp

            import helpers.n8n_client as nc
            nc._CACHE.clear()
            import helpers.manage_variables as mv
            old_argv = sys.argv
            sys.argv = ["manage_variables.py", "--workspace", str(ws),
                        "update", "--env", "dev",
                        "--id", "v1", "--name", "EXISTING", "--value", "new"]
            try:
                mv.main()
            finally:
                sys.argv = old_argv

        url = mock_put.call_args_list[-1].args[0]
        assert url.endswith("/api/v1/variables/v1")
        body = mock_put.call_args_list[-1].kwargs.get("json")
        assert body == {"key": "EXISTING", "value": "new"}


class TestDelete:
    def test_delete_no_force_returns_dry_run(self, tmp_path, capsys):
        ws = _make_workspace(tmp_path)
        with patch("helpers.n8n_client.requests.get") as mock_get, \
             patch("helpers.n8n_client.requests.delete") as mock_delete:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"data": [
                {"id": "v1", "key": "TARGET", "value": "x"},
            ]}
            mock_get.return_value = mock_resp

            import helpers.n8n_client as nc
            nc._CACHE.clear()
            import helpers.manage_variables as mv
            old_argv = sys.argv
            sys.argv = ["manage_variables.py", "--workspace", str(ws),
                        "delete", "--env", "dev", "--id", "v1"]
            try:
                mv.main()
            finally:
                sys.argv = old_argv

        parsed = json.loads(capsys.readouterr().out)
        assert parsed["dry_run"] is True
        assert parsed["id"] == "v1"
        assert parsed["name"] == "TARGET"
        assert "Rerun with --force" in parsed["message"]
        assert mock_delete.call_count == 0

    def test_delete_force_issues_request(self, tmp_path, capsys):
        ws = _make_workspace(tmp_path)
        with patch("helpers.n8n_client.requests.delete") as mock_delete:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"deleted": True}
            mock_delete.return_value = mock_resp

            import helpers.n8n_client as nc
            nc._CACHE.clear()
            import helpers.manage_variables as mv
            old_argv = sys.argv
            sys.argv = ["manage_variables.py", "--workspace", str(ws),
                        "delete", "--env", "dev", "--id", "v1", "--force"]
            try:
                mv.main()
            finally:
                sys.argv = old_argv

        captured = capsys.readouterr().out
        first_block = captured.split("Note:")[0].strip()
        assert json.loads(first_block) == {"deleted": True}
        url = mock_delete.call_args_list[-1].args[0]
        assert url.endswith("/api/v1/variables/v1")
        assert "not version-controlled" in captured


class TestCliShape:
    def test_create_requires_value(self, tmp_path):
        ws = _make_workspace(tmp_path)
        import helpers.manage_variables as mv
        old_argv = sys.argv
        sys.argv = ["manage_variables.py", "--workspace", str(ws),
                    "create", "--env", "dev", "--name", "NEW"]
        try:
            with pytest.raises(SystemExit):
                mv.main()
        finally:
            sys.argv = old_argv
