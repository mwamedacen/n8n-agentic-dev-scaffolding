"""helpers.py tests: unit-level (mocked) + gated real-instance."""
import json
import os
import pytest
from unittest.mock import MagicMock, patch

import helpers
from admin import _load_env, redact_for_debug

GATED = pytest.mark.gated_real
NEED_API = pytest.mark.skipif(
    not os.environ.get("N8N_API_KEY"),
    reason="N8N_API_KEY not set; gated real-instance test skipped",
)


# ---------- unit-level (mocked) ----------

def test_workflow_semantic_diff_ignores_volatile_keys():
    local = {"name": "W", "nodes": [], "connections": {}, "settings": {}}
    live = {
        "name": "W", "nodes": [], "connections": {}, "settings": {},
        "id": "abc", "versionId": "v1", "updatedAt": "2026-01-01",
        "createdAt": "2026-01-01", "active": True, "triggerCount": 0,
        "versionCounter": 7, "activeVersion": None, "activeVersionId": None,
        "description": None, "scopes": [], "tags": [],
    }
    assert helpers.workflow_semantic_diff(local, live) == []


def test_workflow_semantic_diff_catches_real_change():
    local = {"name": "A", "nodes": [], "connections": {}}
    live = {"name": "B", "nodes": [], "connections": {}}
    diff = helpers.workflow_semantic_diff(local, live)
    assert any("name" in d for d in diff)


def test_validate_workflow_json_rejects_bad():
    r = helpers.validate_workflow_json('{"name":"x"}')
    assert r["valid"] is False
    assert r["validator_used"] == "rest-fallback"
    assert r["errors"]


def test_validate_workflow_json_accepts_good():
    good = json.dumps({
        "name": "ok",
        "nodes": [{"name": "T", "type": "n8n-nodes-base.manualTrigger", "parameters": {}}],
        "connections": {},
    })
    r = helpers.validate_workflow_json(good)
    assert r["valid"] is True


def test_redact_for_debug_scrubs_keys_and_credentials():
    rec = {
        "headers": {"Authorization": "Bearer x", "X-N8N-API-KEY": "y"},
        "credentials": {"openAi": {"id": "1", "name": "n", "secret": "leak"}},
        "url": "https://x?api_key=leak&q=v",
        "OPENROUTER_API_KEY": "leak",
        "OTHER_TOKEN": "leak",
    }
    out = redact_for_debug(rec)
    assert out["headers"]["Authorization"] == "<REDACTED>"
    assert out["headers"]["X-N8N-API-KEY"] == "<REDACTED>"
    assert out["credentials"]["openAi"]["secret"] == "<REDACTED>"
    assert out["credentials"]["openAi"]["id"] == "1"  # not a secret
    assert "leak" not in json.dumps(out)


def test_load_env_layering(tmp_path, monkeypatch):
    """Root .env first, .env.<env> overlays with override=True."""
    root = tmp_path / ".env"
    overlay = tmp_path / ".env.dev"
    root.write_text("FOO=root\nBAR=root_only\n")
    overlay.write_text("FOO=overlay\n")
    monkeypatch.setattr("admin.REPO_ROOT", tmp_path)
    monkeypatch.setattr("admin.ENV_DIR", tmp_path / "n8n" / "environments")
    snap = _load_env("dev")
    assert snap["FOO"] == "overlay"
    assert snap["BAR"] == "root_only"


# ---------- gated real-instance ----------

@GATED
@NEED_API
def test_list_workflows_live():
    out = helpers.list_workflows()
    assert isinstance(out, list)
    assert len(out) > 0


@GATED
@NEED_API
def test_demo_smoke_round_trip():
    k = helpers._TEST_WORKFLOW_KEY
    helpers.hydrate(k)
    helpers.deploy(k, activate=True)
    live = helpers.get_workflow(k)
    assert live["name"].startswith("Demo Smoke")
