"""Offline tests for helpers/deploy.py — uses unittest.mock for HTTP."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml


def _harness() -> Path:
    return Path(__file__).parent.parent


def _make_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "n8n-config").mkdir(parents=True)
    (ws / "n8n-workflows-template").mkdir()

    yaml_data = {
        "name": "dev",
        "displayName": "Development",
        "workflowNamePostfix": " [DEV]",
        "n8n": {"instanceName": "localhost:8080"},
        "credentials": {},
        "workflows": {"smoke": {"id": "wf-id-123", "name": "Smoke"}},
    }
    (ws / "n8n-config" / "dev.yml").write_text(yaml.dump(yaml_data))
    (ws / "n8n-config" / ".env.dev").write_text("N8N_API_KEY=fake\n")

    template = {
        "name": "Smoke {{HYDRATE:env:displayName}}",
        "nodes": [{"name": "T", "type": "n8n-nodes-base.webhook", "parameters": {}}],
        "connections": {},
        "settings": {},
    }
    (ws / "n8n-workflows-template" / "smoke.template.json").write_text(json.dumps(template))
    return ws


class TestDeploy:
    def test_deploy_calls_put_then_activate(self, tmp_path):
        ws = _make_workspace(tmp_path)

        with patch("helpers.n8n_client.requests.put") as mock_put, \
             patch("helpers.n8n_client.requests.post") as mock_post:
            mock_put.return_value.raise_for_status.return_value = None
            mock_put.return_value.json.return_value = {"id": "wf-id-123", "active": False}
            mock_post.return_value.raise_for_status.return_value = None
            mock_post.return_value.json.return_value = {"id": "wf-id-123", "active": True}

            from helpers import deploy
            import importlib
            importlib.reload(deploy)
            old_argv = sys.argv
            sys.argv = [
                "deploy.py",
                "--workspace", str(ws),
                "--env", "dev",
                "--workflow-key", "smoke",
            ]
            try:
                deploy.main()
            finally:
                sys.argv = old_argv

        # PUT to /workflows/wf-id-123 happened
        assert mock_put.called
        put_url = mock_put.call_args[0][0]
        assert "workflows/wf-id-123" in put_url
        # POST to /activate happened
        assert mock_post.called
        post_url = mock_post.call_args[0][0]
        assert "activate" in post_url

    def test_deploy_no_activate(self, tmp_path):
        ws = _make_workspace(tmp_path)

        with patch("helpers.n8n_client.requests.put") as mock_put, \
             patch("helpers.n8n_client.requests.post") as mock_post:
            mock_put.return_value.raise_for_status.return_value = None
            mock_put.return_value.json.return_value = {"id": "wf-id-123"}

            from helpers import deploy
            import importlib
            importlib.reload(deploy)
            old_argv = sys.argv
            sys.argv = [
                "deploy.py",
                "--workspace", str(ws),
                "--env", "dev",
                "--workflow-key", "smoke",
                "--no-activate",
            ]
            try:
                deploy.main()
            finally:
                sys.argv = old_argv

        assert mock_put.called
        # POST should NOT be called when --no-activate
        assert not mock_post.called

    def test_deploy_aborts_on_inlined_js_template(self, tmp_path):
        """A template with an inlined-JS Code node must abort deploy before any HTTP call."""
        ws = _make_workspace(tmp_path)

        bad_template = {
            "name": "Bad",
            "nodes": [
                {
                    "name": "Code",
                    "type": "n8n-nodes-base.code",
                    "parameters": {
                        "jsCode": "const stats = {}; return { json: { stats } };",
                    },
                }
            ],
            "connections": {},
            "settings": {},
        }
        (ws / "n8n-workflows-template" / "smoke.template.json").write_text(json.dumps(bad_template))

        with patch("helpers.n8n_client.requests.put") as mock_put, \
             patch("helpers.n8n_client.requests.post") as mock_post:
            from helpers import deploy
            import importlib
            importlib.reload(deploy)
            old_argv = sys.argv
            sys.argv = ["deploy.py", "--workspace", str(ws), "--env", "dev", "--workflow-key", "smoke"]
            try:
                with pytest.raises(SystemExit) as exc:
                    deploy.main()
                assert exc.value.code == 1
            finally:
                sys.argv = old_argv

        assert not mock_put.called, "PUT must not happen when template validation fails"
        assert not mock_post.called, "POST must not happen when template validation fails"

    def test_deploy_strips_disallowed_fields_for_put(self, tmp_path):
        """n8n's PUT API rejects fields like 'active', 'tags', 'id'; deploy.py should drop them."""
        ws = _make_workspace(tmp_path)

        # Add disallowed fields to the template
        template_path = ws / "n8n-workflows-template" / "smoke.template.json"
        data = json.loads(template_path.read_text())
        data["active"] = True
        data["tags"] = []
        data["id"] = "should-be-stripped"
        data["versionId"] = "v1"
        template_path.write_text(json.dumps(data))

        with patch("helpers.n8n_client.requests.put") as mock_put, \
             patch("helpers.n8n_client.requests.post") as mock_post:
            mock_put.return_value.raise_for_status.return_value = None
            mock_put.return_value.json.return_value = {"id": "wf-id-123"}
            mock_post.return_value.raise_for_status.return_value = None
            mock_post.return_value.json.return_value = {}

            from helpers import deploy
            import importlib
            importlib.reload(deploy)
            old_argv = sys.argv
            sys.argv = ["deploy.py", "--workspace", str(ws), "--env", "dev", "--workflow-key", "smoke"]
            try:
                deploy.main()
            finally:
                sys.argv = old_argv

        body = mock_put.call_args.kwargs["json"]
        assert "active" not in body
        assert "tags" not in body
        assert "id" not in body
        assert "versionId" not in body
        assert "nodes" in body
        assert "connections" in body
