"""Offline tests for helpers/add_lock_to_workflow.py — INCR-based contract (B-16/B-17)."""
import json
from pathlib import Path

import pytest

from helpers.add_lock_to_workflow import (
    _insert_lock,
    _make_execute_workflow_node,
    _LOCK_ACQUIRE_NODE_NAME,
    _LOCK_RELEASE_NODE_NAME,
    _DEFAULT_TTL_SECONDS,
    _DEFAULT_MAX_WAIT_SECONDS,
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


def test_default_acquire_inputs_are_eight_field_incr_meta_contract():
    """Task-13 INCR + sidecar-meta primitive takes 8 fields. lock_id, workflow_id,
    and workflow_name flow through so the meta sidecar carries identity for
    ownership-checked release and active error-handler cleanup."""
    tpl = _insert_lock(_minimal_template(), "={{ $execution.id }}")
    inputs = _acquire_node(tpl)["parameters"]["workflowInputs"]["value"]
    assert inputs == {
        "scope": "={{ $execution.id }}",
        "ttl_seconds": _DEFAULT_TTL_SECONDS,
        "execution_id": "={{ $execution.id }}",
        "wait_till_lock_released": True,
        "max_wait_seconds": _DEFAULT_MAX_WAIT_SECONDS,
        "lock_id": "={{ $execution.id }}",
        "workflow_id": "={{ $workflow.id }}",
        "workflow_name": "={{ $workflow.name }}",
    }


def test_fail_fast_flips_wait_till_lock_released_to_false():
    """`fail_fast=True` sets wait_till_lock_released=False; primitive Stop-and-Errors immediately on contention."""
    tpl = _insert_lock(_minimal_template(), "={{ 'shared' }}", fail_fast=True)
    inputs = _acquire_node(tpl)["parameters"]["workflowInputs"]["value"]
    assert inputs["wait_till_lock_released"] is False


def test_ttl_seconds_overridable():
    """`ttl_seconds=300` populates the acquire contract instead of the 86400 default."""
    tpl = _insert_lock(_minimal_template(), "={{ 'pay' }}", ttl_seconds=300)
    inputs = _acquire_node(tpl)["parameters"]["workflowInputs"]["value"]
    assert inputs["ttl_seconds"] == 300


def test_max_wait_seconds_overridable():
    """`max_wait_seconds=30` overrides the 86400 default; useful for webhook-driven callers."""
    tpl = _insert_lock(_minimal_template(), "={{ 'web' }}", max_wait_seconds=30)
    inputs = _acquire_node(tpl)["parameters"]["workflowInputs"]["value"]
    assert inputs["max_wait_seconds"] == 30


def test_release_inputs_carry_scope_and_lock_id():
    """Task-13 ownership-checked release takes scope + lock_id. The release
    primitive GETs the meta sidecar, compares lock_id, and DELs only on match."""
    tpl = _insert_lock(_minimal_template(), "={{ 'sx' }}")
    inputs = _release_node(tpl)["parameters"]["workflowInputs"]["value"]
    assert inputs == {"scope": "={{ 'sx' }}", "lock_id": "={{ $execution.id }}"}


def test_release_does_not_carry_full_workflow_metadata():
    """Release input contract is minimal: scope + lock_id only. Identity comes
    from the meta sidecar Redis key written at acquire-time, not threaded
    through the release call."""
    tpl = _insert_lock(_minimal_template(), "={{ 'a' }}")
    inputs = _release_node(tpl)["parameters"]["workflowInputs"]["value"]
    for forbidden in ("workflow_id", "workflow_name", "execution_id", "ttl_seconds", "wait_till_lock_released", "max_wait_seconds"):
        assert forbidden not in inputs, f"Release should not carry {forbidden!r}, got {inputs}"


def test_acquire_and_release_target_correct_primitives():
    """Acquire targets {{@:env:workflows.lock_acquisition.id}}; release targets workflows.lock_release.id."""
    tpl = _insert_lock(_minimal_template(), "={{ 'a' }}")
    acq = _acquire_node(tpl)["parameters"]["workflowId"]["value"]
    rel = _release_node(tpl)["parameters"]["workflowId"]["value"]
    assert acq == "{{@:env:workflows.lock_acquisition.id}}"
    assert rel == "{{@:env:workflows.lock_release.id}}"


def test_make_execute_workflow_node_passes_inputs_through():
    """`_make_execute_workflow_node` writes the full inputs dict into workflowInputs.value."""
    node = _make_execute_workflow_node(
        "Acquire",
        "{{@:env:workflows.lock_acquisition.id}}",
        [240, 300],
        {"scope": "={{ 'a' }}", "ttl_seconds": 60, "max_wait_seconds": 30},
    )
    assert node["parameters"]["workflowInputs"]["value"] == {
        "scope": "={{ 'a' }}",
        "ttl_seconds": 60,
        "max_wait_seconds": 30,
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


def test_default_max_wait_seconds_matches_ttl():
    """Both defaults are 86400 — long enough to be effectively unbounded for typical use."""
    assert _DEFAULT_MAX_WAIT_SECONDS == 86400
    assert _DEFAULT_TTL_SECONDS == 86400
