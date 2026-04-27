"""Offline tests for helpers/add_lock_to_workflow.py — exercises _insert_lock + _make_execute_workflow_node."""
import json
from pathlib import Path

import pytest

from helpers.add_lock_to_workflow import (
    _insert_lock,
    _make_execute_workflow_node,
    _LOCK_ACQUIRE_NODE_NAME,
    _LOCK_RELEASE_NODE_NAME,
    _DEFAULT_TTL_SECONDS,
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


def test_default_acquire_inputs_carry_full_contract():
    """Default flags emit the six-field acquire contract; wait_till_lock_released defaults to true."""
    tpl = _insert_lock(_minimal_template(), "={{ $execution.id }}")
    inputs = _acquire_node(tpl)["parameters"]["workflowInputs"]["value"]
    assert inputs == {
        "scope": "={{ $execution.id }}",
        "workflow_id": "={{ $workflow.id }}",
        "workflow_name": "={{ $workflow.name }}",
        "wait_till_lock_released": True,
        "execution_id": "={{ $execution.id }}",
        "ttl_seconds": _DEFAULT_TTL_SECONDS,
    }


def test_fail_fast_flips_wait_till_lock_released():
    """`fail_fast=True` sets wait_till_lock_released=False; primitive raises immediately on contention."""
    tpl = _insert_lock(_minimal_template(), "={{ 'shared' }}", fail_fast=True)
    inputs = _acquire_node(tpl)["parameters"]["workflowInputs"]["value"]
    assert inputs["wait_till_lock_released"] is False


def test_ttl_seconds_overridable():
    """`ttl_seconds=300` populates the acquire contract instead of the 86400 default."""
    tpl = _insert_lock(_minimal_template(), "={{ 'pay' }}", ttl_seconds=300)
    inputs = _acquire_node(tpl)["parameters"]["workflowInputs"]["value"]
    assert inputs["ttl_seconds"] == 300


def test_release_node_carries_lock_id_expression_and_scope():
    """The release node passes lock_id (referencing the acquire node's output) plus the original scope."""
    tpl = _insert_lock(_minimal_template(), "={{ 'sx' }}")
    inputs = _release_node(tpl)["parameters"]["workflowInputs"]["value"]
    assert inputs == {
        "lock_id": "={{ $('Lock Acquire').item.json.lock_id }}",
        "scope": "={{ 'sx' }}",
    }


def test_acquire_and_release_target_correct_primitives():
    """Acquire targets {{HYDRATE:env:workflows.lock_acquisition.id}}; release targets workflows.lock_release.id."""
    tpl = _insert_lock(_minimal_template(), "={{ 'a' }}")
    acq = _acquire_node(tpl)["parameters"]["workflowId"]["value"]
    rel = _release_node(tpl)["parameters"]["workflowId"]["value"]
    assert acq == "{{HYDRATE:env:workflows.lock_acquisition.id}}"
    assert rel == "{{HYDRATE:env:workflows.lock_release.id}}"


def test_release_does_not_carry_workflow_id_etc():
    """Release node only needs lock_id + scope. workflow_id/etc. are acquire-only."""
    tpl = _insert_lock(_minimal_template(), "={{ 'a' }}")
    inputs = _release_node(tpl)["parameters"]["workflowInputs"]["value"]
    assert "workflow_id" not in inputs
    assert "workflow_name" not in inputs
    assert "execution_id" not in inputs
    assert "ttl_seconds" not in inputs
    assert "wait_till_lock_released" not in inputs


def test_make_execute_workflow_node_passes_inputs_through():
    """`_make_execute_workflow_node` writes the full inputs dict into workflowInputs.value."""
    node = _make_execute_workflow_node(
        "Acquire",
        "{{HYDRATE:env:workflows.lock_acquisition.id}}",
        [240, 300],
        {"scope": "={{ 'a' }}", "ttl_seconds": 60},
    )
    assert node["parameters"]["workflowInputs"]["value"] == {
        "scope": "={{ 'a' }}",
        "ttl_seconds": 60,
    }


def test_double_insert_refused():
    """Re-inserting on a workflow that already has the acquire node fails."""
    tpl = _insert_lock(_minimal_template(), "={{ 'a' }}")
    with pytest.raises(SystemExit):
        _insert_lock(tpl, "={{ 'a' }}")


def test_downstream_nodes_shifted_right():
    """Original Set node must shift right by 440px to make room for acquire + spacing."""
    tpl_in = _minimal_template()
    original_set_x = next(n for n in tpl_in["nodes"] if n["name"] == "Set")["position"][0]
    tpl = _insert_lock(tpl_in, "={{ 'a' }}")
    new_set_x = next(n for n in tpl["nodes"] if n["name"] == "Set")["position"][0]
    assert new_set_x == original_set_x + 440
