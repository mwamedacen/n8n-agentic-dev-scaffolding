"""Offline tests for helpers/inspect_execution.py — mocks N8nClient HTTP."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

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
        "workflows": {"alpha": {"id": "wf-alpha", "name": "Alpha"}},
    }))
    (ws / "n8n-config" / ".env.dev").write_text("N8N_API_KEY=fake\n")
    return ws


class TestDefaults:
    def test_default_omits_includeData(self, tmp_path, capsys):
        ws = _make_workspace(tmp_path)
        with patch("helpers.n8n_client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"id": "e1", "status": "success"}
            mock_get.return_value = mock_resp

            import helpers.n8n_client as nc
            nc._CACHE.clear()
            import helpers.inspect_execution as ie
            old_argv = sys.argv
            sys.argv = ["inspect_execution.py", "--workspace", str(ws), "--env", "dev",
                        "--execution-id", "e1"]
            try:
                ie.main()
            finally:
                sys.argv = old_argv

        params = mock_get.call_args_list[-1].kwargs.get("params") or {}
        assert "includeData" not in params

        out = capsys.readouterr().out
        assert json.loads(out) == {"id": "e1", "status": "success"}

    def test_include_data_passes_through(self, tmp_path):
        ws = _make_workspace(tmp_path)
        with patch("helpers.n8n_client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"id": "e1", "status": "success", "data": {"a": 1}}
            mock_get.return_value = mock_resp

            import helpers.n8n_client as nc
            nc._CACHE.clear()
            import helpers.inspect_execution as ie
            old_argv = sys.argv
            sys.argv = ["inspect_execution.py", "--workspace", str(ws), "--env", "dev",
                        "--execution-id", "e1", "--include-data"]
            try:
                ie.main()
            finally:
                sys.argv = old_argv

        params = mock_get.call_args_list[-1].kwargs.get("params") or {}
        assert params.get("includeData") == "true"


class TestTruncation:
    def test_truncates_when_data_exceeds_max_size(self, tmp_path, capsys):
        ws = _make_workspace(tmp_path)
        large_blob = {"chunk": "x" * (60 * 1024)}  # 60KB+
        with patch("helpers.n8n_client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"id": "e1", "status": "success", "data": large_blob}
            mock_get.return_value = mock_resp

            import helpers.n8n_client as nc
            nc._CACHE.clear()
            import helpers.inspect_execution as ie
            old_argv = sys.argv
            sys.argv = ["inspect_execution.py", "--workspace", str(ws), "--env", "dev",
                        "--execution-id", "e1", "--include-data"]
            try:
                ie.main()
            finally:
                sys.argv = old_argv

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["data"]["__truncated__"] is True
        assert parsed["data"]["max_size_kb"] == 50
        assert parsed["data"]["original_size_bytes"] > 50 * 1024
        assert "TRUNCATED" in captured.err

    def test_no_truncate_returns_full_payload(self, tmp_path, capsys):
        ws = _make_workspace(tmp_path)
        large_blob = {"chunk": "x" * (60 * 1024)}
        with patch("helpers.n8n_client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"id": "e1", "data": large_blob}
            mock_get.return_value = mock_resp

            import helpers.n8n_client as nc
            nc._CACHE.clear()
            import helpers.inspect_execution as ie
            old_argv = sys.argv
            sys.argv = ["inspect_execution.py", "--workspace", str(ws), "--env", "dev",
                        "--execution-id", "e1", "--include-data", "--no-truncate"]
            try:
                ie.main()
            finally:
                sys.argv = old_argv

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        # No truncation marker — full data returned.
        assert parsed["data"] == large_blob
        assert "TRUNCATED" not in captured.err

    def test_no_truncate_warns_when_over_100kb(self, tmp_path, capsys):
        ws = _make_workspace(tmp_path)
        huge_blob = {"chunk": "x" * (200 * 1024)}  # 200KB
        with patch("helpers.n8n_client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"id": "e1", "data": huge_blob}
            mock_get.return_value = mock_resp

            import helpers.n8n_client as nc
            nc._CACHE.clear()
            import helpers.inspect_execution as ie
            old_argv = sys.argv
            sys.argv = ["inspect_execution.py", "--workspace", str(ws), "--env", "dev",
                        "--execution-id", "e1", "--include-data", "--no-truncate"]
            try:
                ie.main()
            finally:
                sys.argv = old_argv

        captured = capsys.readouterr()
        assert "WARN" in captured.err

    def test_custom_max_size_kb(self, tmp_path, capsys):
        ws = _make_workspace(tmp_path)
        # 30KB blob — under 50 (default) but over 10 (custom).
        blob = {"chunk": "x" * (30 * 1024)}
        with patch("helpers.n8n_client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"id": "e1", "data": blob}
            mock_get.return_value = mock_resp

            import helpers.n8n_client as nc
            nc._CACHE.clear()
            import helpers.inspect_execution as ie
            old_argv = sys.argv
            sys.argv = ["inspect_execution.py", "--workspace", str(ws), "--env", "dev",
                        "--execution-id", "e1", "--include-data", "--max-size-kb", "10"]
            try:
                ie.main()
            finally:
                sys.argv = old_argv

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["data"]["__truncated__"] is True
        assert parsed["data"]["max_size_kb"] == 10

    def test_small_payload_not_truncated(self, tmp_path, capsys):
        ws = _make_workspace(tmp_path)
        small = {"a": 1, "b": "hello"}
        with patch("helpers.n8n_client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"id": "e1", "data": small}
            mock_get.return_value = mock_resp

            import helpers.n8n_client as nc
            nc._CACHE.clear()
            import helpers.inspect_execution as ie
            old_argv = sys.argv
            sys.argv = ["inspect_execution.py", "--workspace", str(ws), "--env", "dev",
                        "--execution-id", "e1", "--include-data"]
            try:
                ie.main()
            finally:
                sys.argv = old_argv

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["data"] == small
        assert "TRUNCATED" not in captured.err


class TestEndpointPath:
    def test_calls_correct_endpoint(self, tmp_path):
        ws = _make_workspace(tmp_path)
        with patch("helpers.n8n_client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"id": "abc-123"}
            mock_get.return_value = mock_resp

            import helpers.n8n_client as nc
            nc._CACHE.clear()
            import helpers.inspect_execution as ie
            old_argv = sys.argv
            sys.argv = ["inspect_execution.py", "--workspace", str(ws), "--env", "dev",
                        "--execution-id", "abc-123"]
            try:
                ie.main()
            finally:
                sys.argv = old_argv

        url = mock_get.call_args_list[-1].args[0]
        assert url.endswith("/api/v1/executions/abc-123")
