"""Round-trip test for hydrate → mock-deploy → resync → diff."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


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
    return ws


class TestRoundTrip:
    def test_hydrate_resync_byte_stable(self, tmp_path):
        """A template that hydrates to B, then dehydrates from B, should equal the original template."""
        ws = _make_workspace(tmp_path)

        original_template = {
            "name": "Smoke {{HYDRATE:env:displayName}}",
            "nodes": [
                {
                    "id": "{{HYDRATE:uuid:webhook-id}}",
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "parameters": {"path": "smoke"},
                    "typeVersion": 1,
                    "position": [100, 200],
                },
                {
                    "id": "{{HYDRATE:uuid:set-id}}",
                    "name": "Set",
                    "type": "n8n-nodes-base.set",
                    "parameters": {"values": {}},
                    "typeVersion": 1,
                    "position": [300, 200],
                },
            ],
            "connections": {
                "Webhook": {"main": [[{"node": "Set", "type": "main", "index": 0}]]},
            },
            "settings": {},
        }
        template_path = ws / "n8n-workflows-template" / "smoke.template.json"
        template_path.write_text(json.dumps(original_template, indent=2))

        # Step 1: hydrate
        from helpers.hydrate import hydrate
        built_path = hydrate("dev", "smoke", ws)
        built = json.loads(built_path.read_text())
        # Resolved values present
        assert built["name"] == "Smoke Development"
        assert "{{HYDRATE" not in json.dumps(built)
        webhook_uuid = built["nodes"][0]["id"]
        set_uuid = built["nodes"][1]["id"]

        # Step 2: simulate n8n returning the workflow with metadata fields added
        live_returned = dict(built)
        live_returned["id"] = "wf-id-123"
        live_returned["active"] = True
        live_returned["versionId"] = "v42"
        live_returned["createdAt"] = "2026-04-26T00:00:00.000Z"
        live_returned["updatedAt"] = "2026-04-26T00:00:00.000Z"
        live_returned["tags"] = []

        # Step 3: dehydrate the live JSON back to a template
        from helpers.dehydrate import dehydrate_data
        text = dehydrate_data(live_returned, "dev", ws, "smoke")
        round_tripped = json.loads(text)

        # No metadata fields survived
        for vol in ("id", "active", "versionId", "createdAt", "updatedAt", "tags"):
            assert vol not in round_tripped

        # Volatile node ids replaced back to UUID placeholders
        assert round_tripped["nodes"][0]["id"] == "{{HYDRATE:uuid:webhook-id}}"
        assert round_tripped["nodes"][1]["id"] == "{{HYDRATE:uuid:set-id}}"

        # Env values reversed back
        assert round_tripped["name"] == "Smoke {{HYDRATE:env:displayName}}"

        # Connections survive
        assert round_tripped["connections"]["Webhook"] == \
            original_template["connections"]["Webhook"]

    def test_diff_empty_for_byte_stable_workflow(self, tmp_path):
        """diff returns empty list for a workflow that wasn't touched in the UI."""
        ws = _make_workspace(tmp_path)

        # Create a hydrated build
        built_dir = ws / "n8n-build" / "dev"
        built_dir.mkdir(parents=True)
        built = {
            "name": "Smoke Development",
            "nodes": [{"id": "n1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "parameters": {}}],
            "connections": {},
            "settings": {},
        }
        (built_dir / "smoke.generated.json").write_text(json.dumps(built))

        # Live returns the same workflow with metadata added
        live = dict(built)
        live["id"] = "wf-id-123"
        live["active"] = True
        live["versionId"] = "v1"
        live["tags"] = []

        from helpers.diff import workflow_semantic_diff
        diff_lines = workflow_semantic_diff(built, live)
        assert diff_lines == [], f"expected empty diff, got: {diff_lines}"

    def test_diff_detects_real_change(self, tmp_path):
        ws = _make_workspace(tmp_path)
        built = {
            "name": "Smoke",
            "nodes": [{"id": "n1", "name": "A", "type": "x", "parameters": {}}],
            "connections": {},
            "settings": {},
        }
        live = {
            "name": "Smoke",
            "nodes": [{"id": "n1", "name": "A", "type": "y", "parameters": {}}],  # type changed
            "connections": {},
            "settings": {},
        }
        from helpers.diff import workflow_semantic_diff
        diff_lines = workflow_semantic_diff(built, live)
        assert any("type" in line for line in diff_lines), diff_lines


class TestResyncCli:
    def test_resync_writes_template(self, tmp_path):
        """resync.py GETs from n8n and writes a template."""
        ws = _make_workspace(tmp_path)

        live_workflow = {
            "id": "wf-id-123",
            "active": True,
            "versionId": "v1",
            "name": "Smoke Development",
            "nodes": [
                {
                    "id": "uuid-from-n8n-1",
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "parameters": {},
                }
            ],
            "connections": {},
            "settings": {},
            "tags": [],
            "createdAt": "2026-04-26T00:00:00.000Z",
            "updatedAt": "2026-04-26T00:00:00.000Z",
        }

        with patch("helpers.n8n_client.requests.get") as mock_get:
            mock_get.return_value.raise_for_status.return_value = None
            mock_get.return_value.json.return_value = live_workflow

            from helpers import resync
            import importlib
            importlib.reload(resync)
            import sys as _sys
            old_argv = _sys.argv
            _sys.argv = [
                "resync.py",
                "--workspace", str(ws),
                "--env", "dev",
                "--workflow-key", "smoke",
            ]
            try:
                resync.main()
            finally:
                _sys.argv = old_argv

        out = ws / "n8n-workflows-template" / "smoke.template.json"
        assert out.exists()
        data = json.loads(out.read_text())
        assert "id" not in data
        assert "active" not in data
