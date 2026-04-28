"""Offline tests for helpers/tidy_workflow.py — layout invariants + fallback paths."""
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from helpers.tidy_workflow import tidy, _bfs_layout, _layout_via_shim

_STICKY_TYPE = "n8n-nodes-base.stickyNote"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _linear_workflow() -> dict:
    """Three nodes in a chain: Webhook → Set → Code."""
    return {
        "name": "Linear",
        "nodes": [
            {"id": "n1", "name": "Webhook", "type": "n8n-nodes-base.webhook",
             "typeVersion": 2, "position": [800, 300], "parameters": {}},
            {"id": "n2", "name": "Set", "type": "n8n-nodes-base.set",
             "typeVersion": 3.4, "position": [800, 300], "parameters": {}},
            {"id": "n3", "name": "Code", "type": "n8n-nodes-base.code",
             "typeVersion": 2, "position": [800, 300], "parameters": {}},
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Set", "type": "main", "index": 0}]]},
            "Set": {"main": [[{"node": "Code", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }


def _workflow_with_sticky() -> dict:
    """One sticky note plus two regular nodes."""
    return {
        "name": "WithSticky",
        "nodes": [
            {"id": "s1", "name": "Note", "type": _STICKY_TYPE,
             "typeVersion": 1, "position": [999, 999], "parameters": {"content": "hello"}},
            {"id": "n1", "name": "Webhook", "type": "n8n-nodes-base.webhook",
             "typeVersion": 2, "position": [800, 300], "parameters": {}},
            {"id": "n2", "name": "Set", "type": "n8n-nodes-base.set",
             "typeVersion": 3.4, "position": [800, 300], "parameters": {}},
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Set", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }


def _cyclic_workflow() -> dict:
    """Two nodes that form a cycle — no roots."""
    return {
        "name": "Cyclic",
        "nodes": [
            {"id": "n1", "name": "A", "type": "n8n-nodes-base.set",
             "typeVersion": 3.4, "position": [800, 300], "parameters": {}},
            {"id": "n2", "name": "B", "type": "n8n-nodes-base.set",
             "typeVersion": 3.4, "position": [800, 300], "parameters": {}},
        ],
        "connections": {
            "A": {"main": [[{"node": "B", "type": "main", "index": 0}]]},
            "B": {"main": [[{"node": "A", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }


def _single_node_workflow() -> dict:
    return {
        "name": "Single",
        "nodes": [
            {"id": "n1", "name": "Webhook", "type": "n8n-nodes-base.webhook",
             "typeVersion": 2, "position": [800, 300], "parameters": {}},
        ],
        "connections": {},
        "settings": {},
    }


# ---------------------------------------------------------------------------
# Sticky-note immutability
# ---------------------------------------------------------------------------

def test_sticky_notes_unchanged_bfs():
    wf = _workflow_with_sticky()
    sticky_before = next(n for n in wf["nodes"] if n["type"] == _STICKY_TYPE)
    result = _bfs_layout(wf)
    sticky_after = next(n for n in result["nodes"] if n["type"] == _STICKY_TYPE)
    assert sticky_after == sticky_before


def test_sticky_notes_unchanged_tidy_with_node_missing():
    """Even when shim is unavailable, sticky notes survive untouched through BFS path."""
    wf = _workflow_with_sticky()
    sticky_before = next(n for n in wf["nodes"] if n["type"] == _STICKY_TYPE)
    with patch("helpers.tidy_workflow.shutil.which", return_value=None):
        result = tidy(wf)
    sticky_after = next(n for n in result["nodes"] if n["type"] == _STICKY_TYPE)
    assert sticky_after == sticky_before


def test_sticky_notes_unchanged_tidy_with_sdk(capsys):
    """SDK output that moves stickies must be corrected by tidy(); non-sticky SDK positions must be kept."""
    wf = _workflow_with_sticky()
    sticky_before = next(n for n in wf["nodes"] if n["type"] == _STICKY_TYPE)

    # SDK moves sticky to [0, 64] AND moves non-sticky nodes to [5000, 5000]
    sdk_out = {**wf, "nodes": [
        {**n, "position": [0, 64]} if n["type"] == _STICKY_TYPE
        else {**n, "position": [5000, 5000]}
        for n in wf["nodes"]
    ]}

    def _sdk_run(*args, **kwargs):
        m = MagicMock()
        m.returncode = 0
        m.stdout = json.dumps(sdk_out)
        m.stderr = ""
        return m

    with patch("helpers.tidy_workflow.shutil.which", return_value="/usr/bin/node"), \
         patch("helpers.tidy_workflow._ensure_sdk", return_value=True), \
         patch("helpers.tidy_workflow.subprocess.run", side_effect=_sdk_run):
        result = tidy(wf)

    sticky_after = next(n for n in result["nodes"] if n["type"] == _STICKY_TYPE)
    assert sticky_after["position"] == sticky_before["position"]
    # Non-sticky positions must come from the SDK, not BFS
    non_stickies = [n for n in result["nodes"] if n["type"] != _STICKY_TYPE]
    assert all(n["position"] == [5000, 5000] for n in non_stickies)


# ---------------------------------------------------------------------------
# No duplicate positions
# ---------------------------------------------------------------------------

def test_no_duplicate_positions_bfs_linear():
    result = _bfs_layout(_linear_workflow())
    non_sticky = [n for n in result["nodes"] if n["type"] != _STICKY_TYPE]
    positions = [tuple(n["position"]) for n in non_sticky]
    assert len(positions) == len(set(positions)), f"Duplicate positions: {positions}"


def test_no_duplicate_positions_bfs_with_sticky():
    result = _bfs_layout(_workflow_with_sticky())
    non_sticky = [n for n in result["nodes"] if n["type"] != _STICKY_TYPE]
    positions = [tuple(n["position"]) for n in non_sticky]
    assert len(positions) == len(set(positions))


# ---------------------------------------------------------------------------
# max_x > min_x for n > 1 non-sticky nodes
# ---------------------------------------------------------------------------

def test_horizontal_spread_linear():
    result = _bfs_layout(_linear_workflow())
    non_sticky = [n for n in result["nodes"] if n["type"] != _STICKY_TYPE]
    assert len(non_sticky) > 1
    xs = [n["position"][0] for n in non_sticky]
    assert max(xs) > min(xs), f"No horizontal spread: xs={xs}"


def test_horizontal_spread_with_sticky():
    result = _bfs_layout(_workflow_with_sticky())
    non_sticky = [n for n in result["nodes"] if n["type"] != _STICKY_TYPE]
    assert len(non_sticky) > 1
    xs = [n["position"][0] for n in non_sticky]
    assert max(xs) > min(xs)


# ---------------------------------------------------------------------------
# Fallback when Node is unavailable
# ---------------------------------------------------------------------------

def test_fallback_bfs_when_no_node(capsys):
    """shutil.which('node') returns None → BFS fallback fires, no crash, spread present."""
    wf = _linear_workflow()
    with patch("helpers.tidy_workflow.shutil.which", return_value=None):
        result = tidy(wf)
    non_sticky = [n for n in result["nodes"] if n["type"] != _STICKY_TYPE]
    xs = [n["position"][0] for n in non_sticky]
    assert max(xs) > min(xs)


# ---------------------------------------------------------------------------
# Subprocess failure → BFS fallback
# ---------------------------------------------------------------------------

def test_fallback_bfs_on_subprocess_failure(capsys):
    """If shim subprocess exits non-zero, BFS still runs.

    stdout carries valid JSON with all-identical positions so that if the
    returncode guard were removed, the passthrough would fail max(xs)>min(xs).
    """
    wf = _linear_workflow()
    # All nodes at same position — BFS must spread them; SDK passthrough would not.
    stuck_out = {**wf, "nodes": [{**n, "position": [800, 300]} for n in wf["nodes"]]}

    def _failing_run(*args, **kwargs):
        m = MagicMock()
        m.returncode = 1
        m.stdout = json.dumps(stuck_out)
        m.stderr = "fake shim error"
        return m

    with patch("helpers.tidy_workflow.shutil.which", return_value="/usr/bin/node"), \
         patch("helpers.tidy_workflow._ensure_sdk", return_value=True), \
         patch("helpers.tidy_workflow.subprocess.run", side_effect=_failing_run):
        result = tidy(wf)

    non_sticky = [n for n in result["nodes"] if n["type"] != _STICKY_TYPE]
    xs = [n["position"][0] for n in non_sticky]
    assert max(xs) > min(xs)


# ---------------------------------------------------------------------------
# Cyclic graph — no crash, insertion-order fallback
# ---------------------------------------------------------------------------

def test_cyclic_graph_no_crash():
    """Pure-cycle graph must not raise; BFS falls back to insertion-order layout."""
    wf = _cyclic_workflow()
    result = _bfs_layout(wf)
    assert len(result["nodes"]) == 2
    non_sticky = [n for n in result["nodes"] if n["type"] != _STICKY_TYPE]
    # Insertion-order: A at start_x, B at start_x + H_GAP
    xs = [n["position"][0] for n in non_sticky]
    assert max(xs) > min(xs)


def test_cyclic_graph_no_duplicate_positions():
    result = _bfs_layout(_cyclic_workflow())
    non_sticky = [n for n in result["nodes"] if n["type"] != _STICKY_TYPE]
    positions = [tuple(n["position"]) for n in non_sticky]
    assert len(positions) == len(set(positions))


# ---------------------------------------------------------------------------
# Idempotence
# ---------------------------------------------------------------------------

def test_idempotence_bfs():
    """Running BFS layout twice produces the same result."""
    wf = _linear_workflow()
    once = _bfs_layout(wf)
    twice = _bfs_layout(once)
    assert once["nodes"] == twice["nodes"]


def test_idempotence_tidy_no_node(capsys):
    """tidy() twice (via BFS) is idempotent."""
    wf = _linear_workflow()
    with patch("helpers.tidy_workflow.shutil.which", return_value=None):
        once = tidy(wf)
    with patch("helpers.tidy_workflow.shutil.which", return_value=None):
        twice = tidy(once)
    assert once["nodes"] == twice["nodes"]


# ---------------------------------------------------------------------------
# Single-node workflow — no crash, no spread requirement
# ---------------------------------------------------------------------------

def test_single_node_no_crash():
    result = _bfs_layout(_single_node_workflow())
    assert len(result["nodes"]) == 1


# ---------------------------------------------------------------------------
# Empty workflow — no crash
# ---------------------------------------------------------------------------

def test_empty_workflow_no_crash():
    wf = {"name": "Empty", "nodes": [], "connections": {}, "settings": {}}
    result = _bfs_layout(wf)
    assert result["nodes"] == []


def test_empty_workflow_tidy_no_crash():
    wf = {"name": "Empty", "nodes": [], "connections": {}, "settings": {}}
    with patch("helpers.tidy_workflow.shutil.which", return_value=None):
        result = tidy(wf)
    assert result["nodes"] == []


# ---------------------------------------------------------------------------
# Sticky-only workflow — no crash, stickies preserved
# ---------------------------------------------------------------------------

def test_sticky_only_workflow_no_crash():
    wf = {
        "name": "StickyOnly",
        "nodes": [
            {"id": "s1", "name": "Note", "type": _STICKY_TYPE,
             "typeVersion": 1, "position": [100, 200], "parameters": {"content": "hi"}},
        ],
        "connections": {},
        "settings": {},
    }
    result = _bfs_layout(wf)
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["position"] == [100, 200]


# ---------------------------------------------------------------------------
# Subprocess exception paths — TimeoutExpired, OSError
# ---------------------------------------------------------------------------

def test_fallback_bfs_on_timeout():
    """subprocess.TimeoutExpired causes BFS fallback, no crash."""
    wf = _linear_workflow()
    with patch("helpers.tidy_workflow.shutil.which", return_value="/usr/bin/node"), \
         patch("helpers.tidy_workflow._ensure_sdk", return_value=True), \
         patch("helpers.tidy_workflow.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="node", timeout=60)):
        result = tidy(wf)
    non_sticky = [n for n in result["nodes"] if n["type"] != _STICKY_TYPE]
    xs = [n["position"][0] for n in non_sticky]
    assert max(xs) > min(xs)


def test_fallback_bfs_on_oserror():
    """OSError (e.g. node binary missing at run time) causes BFS fallback, no crash."""
    wf = _linear_workflow()
    with patch("helpers.tidy_workflow.shutil.which", return_value="/usr/bin/node"), \
         patch("helpers.tidy_workflow._ensure_sdk", return_value=True), \
         patch("helpers.tidy_workflow.subprocess.run",
               side_effect=OSError("cannot execute")):
        result = tidy(wf)
    non_sticky = [n for n in result["nodes"] if n["type"] != _STICKY_TYPE]
    xs = [n["position"][0] for n in non_sticky]
    assert max(xs) > min(xs)


# ---------------------------------------------------------------------------
# Disconnected components — each component gets its own row
# ---------------------------------------------------------------------------

def test_disconnected_components_no_duplicate_positions():
    """Two independent chains must produce unique positions."""
    wf = {
        "name": "Disconnected",
        "nodes": [
            {"id": "a1", "name": "A1", "type": "n8n-nodes-base.set",
             "typeVersion": 3.4, "position": [0, 0], "parameters": {}},
            {"id": "a2", "name": "A2", "type": "n8n-nodes-base.set",
             "typeVersion": 3.4, "position": [0, 0], "parameters": {}},
            {"id": "b1", "name": "B1", "type": "n8n-nodes-base.set",
             "typeVersion": 3.4, "position": [0, 0], "parameters": {}},
            {"id": "b2", "name": "B2", "type": "n8n-nodes-base.set",
             "typeVersion": 3.4, "position": [0, 0], "parameters": {}},
        ],
        "connections": {
            "A1": {"main": [[{"node": "A2", "type": "main", "index": 0}]]},
            "B1": {"main": [[{"node": "B2", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }
    result = _bfs_layout(wf)
    positions = [tuple(n["position"]) for n in result["nodes"]]
    assert len(positions) == len(set(positions)), f"Duplicate positions: {positions}"
