"""Validation smoke for the four new queue primitives."""
import json
from pathlib import Path

import pytest
import yaml

from helpers.validate import validate_workflow_json
from helpers.placeholder import validator as placeholder_validator


_PRIMITIVES_DIR = Path(__file__).parent.parent / "primitives" / "workflows"


@pytest.mark.parametrize(
    "primitive",
    [
        "queue_publish",
        "queue_pop",
        "queue_ack",
        "error_handler_queue_cleanup",
    ],
)
def test_queue_primitive_code_nodes_use_javascript_capital_s(primitive):
    """Every Code node in every shipped queue primitive must use `language: \"javaScript\"` (capital S).

    n8n's Code v2 schema enum is `'javaScript' | 'pythonNative'`. The lowercase
    'javascript' is silently coerced to the default but is NOT valid input —
    templates that ship with the wrong casing fail to load correctly in the n8n UI.
    """
    path = _PRIMITIVES_DIR / f"{primitive}.template.json"
    data = json.loads(path.read_text())
    code_nodes = [n for n in data.get("nodes", []) if n.get("type") == "n8n-nodes-base.code"]
    assert code_nodes, f"{primitive}: no Code nodes found — test fixture is stale"
    for node in code_nodes:
        lang = node.get("parameters", {}).get("language")
        assert lang == "javaScript", (
            f"{primitive}: Code node {node.get('name')!r} has language={lang!r}, "
            "expected 'javaScript' (capital S)."
        )


@pytest.mark.parametrize(
    "primitive",
    [
        "queue_publish",
        "queue_pop",
        "queue_ack",
        "error_handler_queue_cleanup",
    ],
)
def test_queue_primitive_code_nodes_have_marker(primitive):
    """Every Code node body must start with the @n8n-evol-I:primitive marker.
    Without it, validate.py rejects the template under pure-function discipline.
    """
    path = _PRIMITIVES_DIR / f"{primitive}.template.json"
    data = json.loads(path.read_text())
    for node in data.get("nodes", []):
        if node.get("type") != "n8n-nodes-base.code":
            continue
        code = node.get("parameters", {}).get("jsCode", "") or node.get("parameters", {}).get("pythonCode", "")
        assert code.lstrip().startswith("// @n8n-evol-I:primitive"), (
            f"{primitive}: Code node {node.get('name')!r} missing primitive marker; "
            "validate.py would reject the template."
        )


@pytest.mark.parametrize(
    "primitive",
    [
        "queue_publish",
        "queue_pop",
        "queue_ack",
        "error_handler_queue_cleanup",
    ],
)
def test_queue_primitive_template_validates(primitive, tmp_path):
    """Each primitive template passes structural validation (template source)."""
    path = _PRIMITIVES_DIR / f"{primitive}.template.json"
    text = path.read_text()
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert valid, errors


def _make_stub_workspace(tmp_path: Path) -> Path:
    """Stub workspace: copy queue primitives + stub env yml so hydrate works."""
    ws = tmp_path / "ws"
    (ws / "n8n-config").mkdir(parents=True)
    (ws / "n8n-workflows-template").mkdir()
    for prim in ("queue_publish", "queue_pop", "queue_ack", "error_handler_queue_cleanup"):
        src = _PRIMITIVES_DIR / f"{prim}.template.json"
        dst = ws / "n8n-workflows-template" / f"{prim}.template.json"
        dst.write_text(src.read_text())
    env_data = {
        "name": "test",
        "displayName": "Test",
        "workflowNamePostfix": " [TEST]",
        "n8n": {"instanceName": "localhost:8080"},
        "credentials": {
            "redis_rest": {"id": "rest-1", "name": "Upstash REST", "type": "httpHeaderAuth"},
        },
        "workflows": {
            "queue_publish": {"id": "qp-1", "name": "Queue Publish"},
            "queue_pop": {"id": "qpop-1", "name": "Queue Pop"},
            "queue_ack": {"id": "qa-1", "name": "Queue Ack"},
            "error_handler_queue_cleanup": {"id": "ehqc-1", "name": "Error Handler Queue Cleanup"},
        },
        "queueScopes": ["test-stream"],
    }
    (ws / "n8n-config" / "test.yml").write_text(yaml.dump(env_data))
    (ws / "n8n-config" / ".env.test").write_text("N8N_API_KEY=fake\nUPSTASH_REDIS_REST_URL=https://example.upstash.io\n")
    return ws


@pytest.mark.parametrize(
    "primitive",
    [
        "queue_publish",
        "queue_pop",
        "queue_ack",
        "error_handler_queue_cleanup",
    ],
)
def test_queue_primitive_hydrates_clean(primitive, tmp_path):
    """Each queue primitive hydrates without leaving residual placeholders, and the
    resulting JSON is parseable + structurally valid as a built workflow.
    """
    from helpers.hydrate import hydrate

    ws = _make_stub_workspace(tmp_path)
    out = hydrate("test", primitive, ws, strict=True)
    assert out.is_file()
    text = out.read_text()
    residuals = placeholder_validator.check_residuals(text)
    assert residuals == [], f"{primitive}: residual placeholders {residuals}"
    json.loads(text)  # raises if invalid
    valid, errors = validate_workflow_json(text, source="built", workspace=ws)
    assert valid, errors
