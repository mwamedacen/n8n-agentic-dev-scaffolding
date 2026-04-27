"""Offline tests for helpers/add_lock_to_workflow.py — exercises _insert_lock + _make_execute_workflow_node."""
import json
from pathlib import Path

import pytest

from helpers.add_lock_to_workflow import (
    _insert_lock,
    _make_execute_workflow_node,
    _LOCK_ACQUIRE_NODE_NAME,
    _LOCK_RELEASE_NODE_NAME,
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


def _acquire_node(template: dict) -> dict:
    return next(n for n in template["nodes"] if n["name"] == _LOCK_ACQUIRE_NODE_NAME)


def _release_node(template: dict) -> dict:
    return next(n for n in template["nodes"] if n["name"] == _LOCK_RELEASE_NODE_NAME)


def test_default_inserts_only_scope():
    """Default flags (no wait-mode) must NOT emit maxWaitMs/pollIntervalMs/ttlSeconds — primitive defaults apply."""
    tpl = _insert_lock(_minimal_template(), "={{ $execution.id }}")
    inputs = _acquire_node(tpl)["parameters"]["workflowInputs"]["value"]
    assert inputs == {"scope": "={{ $execution.id }}"}, inputs


def test_max_wait_ms_populated():
    """--max-wait-ms 1000 sets maxWaitMs=1000 in workflowInputs.value of the acquire node."""
    tpl = _insert_lock(_minimal_template(), "={{ $execution.id }}", max_wait_ms=1000)
    inputs = _acquire_node(tpl)["parameters"]["workflowInputs"]["value"]
    assert inputs.get("maxWaitMs") == 1000, inputs
    assert "pollIntervalMs" not in inputs
    assert "ttlSeconds" not in inputs


def test_poll_interval_non_default_populated():
    """Non-default poll-interval is emitted; defaults stay omitted."""
    tpl = _insert_lock(_minimal_template(), "={{ 'a' }}", poll_interval_ms=500)
    inputs = _acquire_node(tpl)["parameters"]["workflowInputs"]["value"]
    assert inputs.get("pollIntervalMs") == 500, inputs
    assert "maxWaitMs" not in inputs
    assert "ttlSeconds" not in inputs


def test_ttl_seconds_non_default_populated():
    tpl = _insert_lock(_minimal_template(), "={{ 'a' }}", ttl_seconds=120)
    inputs = _acquire_node(tpl)["parameters"]["workflowInputs"]["value"]
    assert inputs.get("ttlSeconds") == 120, inputs
    assert "maxWaitMs" not in inputs
    assert "pollIntervalMs" not in inputs


def test_all_wait_flags_populated_together():
    tpl = _insert_lock(
        _minimal_template(),
        "={{ 'shared' }}",
        max_wait_ms=2000,
        poll_interval_ms=100,
        ttl_seconds=30,
    )
    inputs = _acquire_node(tpl)["parameters"]["workflowInputs"]["value"]
    assert inputs == {
        "scope": "={{ 'shared' }}",
        "maxWaitMs": 2000,
        "pollIntervalMs": 100,
        "ttlSeconds": 30,
    }


def test_release_node_unaffected_by_wait_flags():
    """Wait flags are acquire-only. Release node always carries just `scope`."""
    tpl = _insert_lock(
        _minimal_template(),
        "={{ 'x' }}",
        max_wait_ms=2000,
        poll_interval_ms=100,
        ttl_seconds=30,
    )
    inputs = _release_node(tpl)["parameters"]["workflowInputs"]["value"]
    assert inputs == {"scope": "={{ 'x' }}"}


def test_make_execute_workflow_node_extra_inputs_merged():
    """`_make_execute_workflow_node`'s extra_inputs param is merged into workflowInputs.value alongside scope."""
    node = _make_execute_workflow_node(
        "Acquire",
        "{{HYDRATE:env:workflows.lock_acquisition.id}}",
        [240, 300],
        "={{ 'a' }}",
        extra_inputs={"maxWaitMs": 500},
    )
    assert node["parameters"]["workflowInputs"]["value"] == {
        "scope": "={{ 'a' }}",
        "maxWaitMs": 500,
    }


def test_make_execute_workflow_node_no_extras_keeps_scope_only():
    """Without extra_inputs, only scope appears in value (preserves backward compat)."""
    node = _make_execute_workflow_node(
        "Acquire",
        "{{HYDRATE:env:workflows.lock_acquisition.id}}",
        [240, 300],
        "={{ 'a' }}",
    )
    assert node["parameters"]["workflowInputs"]["value"] == {"scope": "={{ 'a' }}"}


def test_make_execute_workflow_node_none_extras_keeps_scope_only():
    """extra_inputs=None must behave the same as omitting the param."""
    node = _make_execute_workflow_node(
        "Acquire",
        "{{HYDRATE:env:workflows.lock_acquisition.id}}",
        [240, 300],
        "={{ 'a' }}",
        extra_inputs=None,
    )
    assert node["parameters"]["workflowInputs"]["value"] == {"scope": "={{ 'a' }}"}
