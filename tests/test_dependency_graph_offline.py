"""Offline tests for helpers/dependency_graph.py — workspace reads + mocked HTTP for live."""
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
        "credentials": {
            "redis": {"id": "cred-redis-1", "name": "Redis", "type": "redis"},
        },
        "workflows": {
            "alpha": {"id": "wf-alpha-id", "name": "Alpha"},
            "beta":  {"id": "wf-beta-id",  "name": "Beta"},
            "handler": {"id": "wf-handler-id", "name": "Handler"},
        },
    }))
    (ws / "n8n-config" / ".env.dev").write_text("N8N_API_KEY=fake\n")
    return ws


def _write_template(ws: Path, key: str, body: dict) -> None:
    (ws / "n8n-workflows-template" / f"{key}.template.json").write_text(json.dumps(body))


def _alpha_template_calling_beta() -> dict:
    """Alpha is an Execute-Workflow caller targeting Beta + uses Redis."""
    return {
        "name": "alpha",
        "nodes": [
            {
                "name": "Run Beta",
                "type": "n8n-nodes-base.executeWorkflow",
                "typeVersion": 1.2,
                "parameters": {
                    "workflowId": {
                        "__rl": True,
                        "value": "{{HYDRATE:env:workflows.beta.id}}",
                        "mode": "id",
                    },
                },
            },
            {
                "name": "Redis GET",
                "type": "n8n-nodes-base.redis",
                "typeVersion": 1,
                "parameters": {"operation": "get", "key": "x"},
                "credentials": {
                    "redis": {"id": "cred-redis-1", "name": "Redis"},
                },
            },
        ],
        "settings": {
            "errorWorkflow": "{{HYDRATE:env:workflows.handler.id}}",
        },
    }


def _beta_template_using_redis() -> dict:
    return {
        "name": "beta",
        "nodes": [
            {
                "name": "Redis SET",
                "type": "n8n-nodes-base.redis",
                "typeVersion": 1,
                "parameters": {"operation": "set", "key": "y"},
                "credentials": {
                    "redis": {"id": "cred-redis-1", "name": "Redis"},
                },
            },
        ],
    }


class TestTemplateSource:
    def test_calls_resolved_to_keys(self, tmp_path):
        ws = _make_workspace(tmp_path)
        _write_template(ws, "alpha", _alpha_template_calling_beta())
        _write_template(ws, "beta", _beta_template_using_redis())

        from helpers.dependency_graph import build_graph
        g = build_graph("dev", ws, "template")
        assert g["calls"] == {"alpha": ["beta"]}
        assert g["error_handlers"]["alpha"] == "handler"

    def test_credential_groups_collect_workflows(self, tmp_path):
        ws = _make_workspace(tmp_path)
        _write_template(ws, "alpha", _alpha_template_calling_beta())
        _write_template(ws, "beta", _beta_template_using_redis())

        from helpers.dependency_graph import build_graph
        g = build_graph("dev", ws, "template")
        assert g["credential_groups"]["cred-redis-1"] == ["alpha", "beta"]

    def test_workflow_key_filter_focuses_on_one(self, tmp_path):
        ws = _make_workspace(tmp_path)
        _write_template(ws, "alpha", _alpha_template_calling_beta())
        _write_template(ws, "beta", _beta_template_using_redis())

        from helpers.dependency_graph import build_graph
        g = build_graph("dev", ws, "template", workflow_key="alpha")
        assert "alpha" in g["calls"]
        assert "beta" not in g["calls"]
        # Beta's credential reference is not in scope when filtered to alpha.
        assert g["credential_groups"].get("cred-redis-1") == ["alpha"]

    def test_common_yml_error_pairs_merged(self, tmp_path):
        ws = _make_workspace(tmp_path)
        _write_template(ws, "alpha", _alpha_template_calling_beta())
        # Common.yml maps 'beta' to 'handler' even though beta has no settings.errorWorkflow.
        (ws / "n8n-config" / "common.yml").write_text(yaml.dump({
            "error_source_to_handler": {"beta": "handler"},
        }))
        _write_template(ws, "beta", _beta_template_using_redis())

        from helpers.dependency_graph import build_graph
        g = build_graph("dev", ws, "template")
        assert g["error_handlers"]["beta"] == "handler"
        assert g["error_handlers"]["alpha"] == "handler"


class TestLiveSource:
    def test_live_source_reads_n8n_workflows(self, tmp_path):
        ws = _make_workspace(tmp_path)
        # Templates absent — live should still produce a graph keyed by yaml keys.
        live_payload = {"data": [
            {
                "id": "wf-alpha-id",
                "name": "Alpha live",
                "nodes": [
                    {
                        "name": "Run Beta",
                        "type": "n8n-nodes-base.executeWorkflow",
                        "parameters": {
                            "workflowId": {"__rl": True, "value": "wf-beta-id", "mode": "id"},
                        },
                    },
                ],
                "settings": {"errorWorkflow": "wf-handler-id"},
            },
            {
                "id": "wf-beta-id",
                "name": "Beta live",
                "nodes": [],
                "settings": {},
            },
        ]}

        with patch("helpers.n8n_client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = live_payload
            mock_get.return_value = mock_resp

            # Reset the module-level client cache so this test's patch is honored.
            import helpers.n8n_client as nc
            nc._CACHE.clear()

            from helpers.dependency_graph import build_graph
            g = build_graph("dev", ws, "live")

        assert g["calls"]["alpha"] == ["beta"]
        assert g["error_handlers"]["alpha"] == "handler"


class TestOutputModes:
    def test_text_output_is_human_readable(self, tmp_path, capsys):
        ws = _make_workspace(tmp_path)
        _write_template(ws, "alpha", _alpha_template_calling_beta())

        import importlib
        import helpers.dependency_graph as dg
        importlib.reload(dg)
        old_argv = sys.argv
        sys.argv = ["dependency_graph.py", "--workspace", str(ws), "--env", "dev",
                    "--source", "template"]
        try:
            dg.main()
        finally:
            sys.argv = old_argv

        out = capsys.readouterr().out
        assert "calls (Execute Workflow):" in out
        assert "alpha → beta" in out
        assert "error_handlers" in out
        assert "credential_groups" in out

    def test_json_flag_emits_single_document(self, tmp_path, capsys):
        ws = _make_workspace(tmp_path)
        _write_template(ws, "alpha", _alpha_template_calling_beta())

        import importlib
        import helpers.dependency_graph as dg
        importlib.reload(dg)
        old_argv = sys.argv
        sys.argv = ["dependency_graph.py", "--workspace", str(ws), "--env", "dev",
                    "--source", "template", "--json"]
        try:
            dg.main()
        finally:
            sys.argv = old_argv

        out = capsys.readouterr().out
        doc = json.loads(out)
        assert doc["calls"]["alpha"] == ["beta"]
        assert doc["error_handlers"]["alpha"] == "handler"


class TestUnknownIdsFallThrough:
    def test_unknown_target_id_passes_through_as_raw(self, tmp_path):
        ws = _make_workspace(tmp_path)
        body = {
            "name": "alpha",
            "nodes": [
                {
                    "name": "Run unknown",
                    "type": "n8n-nodes-base.executeWorkflow",
                    "parameters": {
                        "workflowId": {"__rl": True, "value": "wf-mystery-id", "mode": "id"},
                    },
                },
            ],
        }
        _write_template(ws, "alpha", body)

        from helpers.dependency_graph import build_graph
        g = build_graph("dev", ws, "template")
        # An unknown id falls through unchanged so the agent can spot the dangling reference.
        assert g["calls"]["alpha"] == ["wf-mystery-id"]
