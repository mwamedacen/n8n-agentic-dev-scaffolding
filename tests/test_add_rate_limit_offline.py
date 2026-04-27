"""Offline tests for helpers/add_rate_limit_to_workflow.py — exercises _insert_rate_limit."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from helpers.add_rate_limit_to_workflow import (
    _insert_rate_limit,
    _RATE_LIMIT_NODE_NAME,
    _IF_NODE_NAME,
    _DENIED_PASSTHROUGH_NAME,
    _DENIED_STOP_NAME,
)


def _minimal_template() -> dict:
    """A tiny workflow: trigger → terminal Set node."""
    return {
        "name": "Smoke",
        "nodes": [
            {
                "id": "t1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [240, 300],
                "parameters": {"path": "smoke"},
            },
            {
                "id": "s1",
                "name": "Set",
                "type": "n8n-nodes-base.set",
                "typeVersion": 3.4,
                "position": [460, 300],
                "parameters": {},
            },
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Set", "type": "main", "index": 0}]],
            },
        },
        "settings": {},
    }


def _node(template: dict, name: str) -> dict:
    return next(n for n in template["nodes"] if n["name"] == name)


def test_passthrough_default_wires_set_on_else():
    """Default --on-denied passthrough → If's else branch connects to a Set node."""
    tpl = _insert_rate_limit(
        _minimal_template(),
        scope_expr="={{ $json.userId }}",
        limit=10,
        window_seconds=60,
    )
    # Nodes added: rate-limit, if, denied-passthrough Set
    rl = _node(tpl, _RATE_LIMIT_NODE_NAME)
    if_node = _node(tpl, _IF_NODE_NAME)
    denied = _node(tpl, _DENIED_PASSTHROUGH_NAME)

    assert rl["type"] == "n8n-nodes-base.executeWorkflow"
    assert if_node["type"] == "n8n-nodes-base.if"
    assert denied["type"] == "n8n-nodes-base.set"

    # rate-limit inputs carry scope/limit/windowSeconds
    rl_inputs = rl["parameters"]["workflowInputs"]["value"]
    assert rl_inputs == {
        "scope": "={{ $json.userId }}",
        "limit": 10,
        "windowSeconds": 60,
    }

    # If condition is the canonical $json.allowed === true expression
    cond = if_node["parameters"]["conditions"]["conditions"][0]
    assert cond["leftValue"] == "={{ $json.allowed === true }}"

    # Wiring: trigger → rate_limit → if; if[0]=allowed → original first_branch; if[1]=denied → Set
    conns = tpl["connections"]
    assert conns["Webhook"] == {"main": [[{"node": _RATE_LIMIT_NODE_NAME, "type": "main", "index": 0}]]}
    assert conns[_RATE_LIMIT_NODE_NAME] == {"main": [[{"node": _IF_NODE_NAME, "type": "main", "index": 0}]]}
    if_main = conns[_IF_NODE_NAME]["main"]
    assert len(if_main) == 2
    assert if_main[0] == [{"node": "Set", "type": "main", "index": 0}]
    assert if_main[1] == [{"node": _DENIED_PASSTHROUGH_NAME, "type": "main", "index": 0}]


def test_on_denied_stop_wires_stop_and_error():
    """--on-denied stop → else branch connects to a stopAndError node."""
    tpl = _insert_rate_limit(
        _minimal_template(),
        scope_expr="={{ 'global' }}",
        limit=5,
        window_seconds=30,
        on_denied="stop",
    )
    denied = _node(tpl, _DENIED_STOP_NAME)
    assert denied["type"] == "n8n-nodes-base.stopAndError"

    if_main = tpl["connections"][_IF_NODE_NAME]["main"]
    assert if_main[1] == [{"node": _DENIED_STOP_NAME, "type": "main", "index": 0}]

    # Passthrough Set must NOT be present.
    assert not any(n["name"] == _DENIED_PASSTHROUGH_NAME for n in tpl["nodes"])


def test_on_denied_error_wires_stop_and_error():
    """--on-denied error → also a stopAndError node (errors trigger errorWorkflow if configured)."""
    tpl = _insert_rate_limit(
        _minimal_template(),
        scope_expr="={{ 'global' }}",
        limit=5,
        window_seconds=30,
        on_denied="error",
    )
    denied = _node(tpl, _DENIED_STOP_NAME)
    assert denied["type"] == "n8n-nodes-base.stopAndError"


def test_invalid_on_denied_rejected():
    """Unknown --on-denied value raises SystemExit."""
    with pytest.raises(SystemExit):
        _insert_rate_limit(
            _minimal_template(),
            scope_expr="={{ 'a' }}",
            limit=5,
            window_seconds=30,
            on_denied="bogus",
        )


def test_refuses_double_insert():
    """Re-inserting on a workflow that already has the rate-limit node fails."""
    tpl = _insert_rate_limit(
        _minimal_template(),
        scope_expr="={{ 'a' }}",
        limit=5,
        window_seconds=30,
    )
    with pytest.raises(SystemExit):
        _insert_rate_limit(tpl, scope_expr="={{ 'a' }}", limit=5, window_seconds=30)


def test_downstream_nodes_shifted_right():
    """The original Set node (and any other non-trigger node) must be shifted right by 660px."""
    tpl_in = _minimal_template()
    original_set_x = _node(tpl_in, "Set")["position"][0]

    tpl = _insert_rate_limit(tpl_in, scope_expr="={{ 'a' }}", limit=5, window_seconds=30)
    new_set_x = _node(tpl, "Set")["position"][0]
    assert new_set_x == original_set_x + 660


def test_cli_refuses_when_primitive_missing(tmp_path):
    """CLI exits non-zero when rate_limit_check.template.json isn't in the workspace."""
    ws = tmp_path / "ws"
    (ws / "n8n-workflows-template").mkdir(parents=True)
    (ws / "n8n-config").mkdir()
    # Drop a workflow template but no primitive.
    template = {
        "name": "App",
        "nodes": [
            {
                "id": "t1", "name": "Webhook",
                "type": "n8n-nodes-base.webhook", "typeVersion": 2,
                "position": [240, 300], "parameters": {"path": "smoke"},
            },
        ],
        "connections": {},
        "settings": {},
    }
    (ws / "n8n-workflows-template" / "app.template.json").write_text(json.dumps(template))

    cmd = [
        sys.executable,
        str(Path(__file__).parent.parent / "helpers" / "add_rate_limit_to_workflow.py"),
        "--workspace", str(ws),
        "--workflow-key", "app",
        "--limit", "10",
        "--window-seconds", "60",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode != 0, r.stdout
    assert "rate_limit_check" in r.stderr, r.stderr


def test_cli_succeeds_with_primitive_present(tmp_path):
    """CLI runs end-to-end when rate_limit_check primitive is in the workspace."""
    ws = tmp_path / "ws"
    (ws / "n8n-workflows-template").mkdir(parents=True)
    (ws / "n8n-config").mkdir()
    # Drop the rate_limit_check primitive (just a stub — the helper only checks for existence).
    (ws / "n8n-workflows-template" / "rate_limit_check.template.json").write_text("{}")
    template = {
        "name": "App",
        "nodes": [
            {
                "id": "t1", "name": "Webhook",
                "type": "n8n-nodes-base.webhook", "typeVersion": 2,
                "position": [240, 300], "parameters": {"path": "smoke"},
            },
        ],
        "connections": {},
        "settings": {},
    }
    (ws / "n8n-workflows-template" / "app.template.json").write_text(json.dumps(template))

    cmd = [
        sys.executable,
        str(Path(__file__).parent.parent / "helpers" / "add_rate_limit_to_workflow.py"),
        "--workspace", str(ws),
        "--workflow-key", "app",
        "--limit", "10",
        "--window-seconds", "60",
        "--scope-expression", "={{ $json.userId }}",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

    # Verify the template was rewritten with the gate.
    out = json.loads((ws / "n8n-workflows-template" / "app.template.json").read_text())
    node_names = [n["name"] for n in out["nodes"]]
    assert _RATE_LIMIT_NODE_NAME in node_names
    assert _IF_NODE_NAME in node_names
    assert _DENIED_PASSTHROUGH_NAME in node_names
