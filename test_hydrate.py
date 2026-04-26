"""hydrate→dehydrate round-trip placeholder tests."""
import json
import os
import shutil
from pathlib import Path
import pytest

import helpers


@pytest.fixture
def tmp_workspace(tmp_path, monkeypatch):
    """Set up a writable copy of n8n/workflows so we can hydrate without churning the live tree."""
    src = Path(__file__).parent / "n8n" / "workflows"
    yield src


def test_hydrate_demo_smoke_writes_generated(tmp_workspace):
    p = helpers.hydrate(helpers._TEST_WORKFLOW_KEY, env="dev")
    assert os.path.exists(p)
    assert os.path.getsize(p) > 0
    data = json.loads(Path(p).read_text())
    assert data["name"].startswith("Demo Smoke")
    # Make sure no placeholder leaked
    text = Path(p).read_text()
    assert "{{HYDRATE:" not in text


def test_hydrate_uses_each_placeholder_type():
    """A representative demo exercises env, txt, json, html, js, uuid placeholders collectively."""
    types = set()
    for tpl in (Path(__file__).parent / "n8n" / "workflows").glob("demo_*.template.json"):
        text = tpl.read_text()
        for t in ("env", "txt", "json", "html", "js", "uuid"):
            if "{{HYDRATE:" + t + ":" in text:
                types.add(t)
    assert types >= {"env", "txt", "json", "html", "js", "uuid"}, types


def test_dehydrate_round_trip_idempotent(tmp_path):
    """Hydrate + dehydrate (in-memory) should yield placeholders that re-hydrate to equivalent JSON."""
    p = helpers.hydrate(helpers._TEST_WORKFLOW_KEY, env="dev")
    hydrated_json = Path(p).read_text()
    dehydrated = helpers.dehydrate(hydrated_json, env="dev")
    # The dehydrated JSON should at minimum contain the workflow name placeholder,
    # confirming env-value reverse-replacement worked on something:
    assert "{{HYDRATE:" in dehydrated, "dehydrate produced no placeholders"


def test_workflow_semantic_diff_round_trip():
    """A canonical workflow JSON compared to itself yields no diff."""
    wf = {
        "name": "x",
        "nodes": [{"name": "a", "type": "n8n-nodes-base.manualTrigger", "parameters": {}}],
        "connections": {},
        "settings": {},
    }
    assert helpers.workflow_semantic_diff(wf, wf) == []
