"""Unit tests for the task #13 lock-identity / ownership-release / active-cleanup restoration.

Each test pins a behavior the user requested be restored from their original
templates — if a future refactor breaks the contract, the test fails loudly.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

PRIMITIVES_DIR = Path(__file__).resolve().parents[1] / "primitives" / "workflows"


def _load_primitive(key: str) -> dict:
    return json.loads((PRIMITIVES_DIR / f"{key}.template.json").read_text())


def _node(template: dict, name: str) -> dict | None:
    for n in template.get("nodes", []):
        if n.get("name") == name:
            return n
    return None


# ---------------------------------------------------------------------------
# Acquire-side: lock_id + meta sidecar
# ---------------------------------------------------------------------------


def test_acquire_emits_lock_id_in_context() -> None:
    """Build Lock Context must surface lock_id, meta_key, workflow_id,
    workflow_name, locked_at — the fields needed for ownership-checked release."""
    primitive = _load_primitive("lock_acquisition")
    ctx = _node(primitive, "Build Lock Context")
    assert ctx is not None
    js = ctx["parameters"]["jsCode"]
    for needed in ("lock_id", "meta_key", "workflow_id", "workflow_name", "locked_at"):
        assert needed in js, f"Build Lock Context must surface {needed!r} in its returned object"


def test_acquire_writes_meta_sidecar_after_acquired_branch() -> None:
    """After Acquired? returns true, the primitive must SET an `n8n-lock-<scope>:meta`
    sidecar with the JSON identity payload."""
    primitive = _load_primitive("lock_acquisition")
    set_meta = _node(primitive, "Set Lock Meta")
    assert set_meta is not None, "task #13 requires a 'Set Lock Meta' node"
    assert set_meta["type"] == "n8n-nodes-base.redis"
    assert set_meta["parameters"]["operation"] == "set"
    # The meta key must reference Build Lock Context's `meta_key` field.
    assert "meta_key" in set_meta["parameters"]["key"]
    # Value must include all 5 identity fields.
    val = set_meta["parameters"]["value"]
    for needed in ("lock_id", "workflow_id", "workflow_name", "execution_id", "locked_at"):
        assert needed in val, f"Set Lock Meta value must include {needed!r}"


def test_acquired_branch_wires_to_set_meta() -> None:
    """The Acquired? true-branch must route to Set Lock Meta (was empty pre-task-13)."""
    primitive = _load_primitive("lock_acquisition")
    acquired_out = primitive["connections"]["Acquired?"]["main"]
    # Index 0 is the true-branch (acquired); must route to Set Lock Meta.
    true_branch = acquired_out[0]
    assert any(c["node"] == "Set Lock Meta" for c in true_branch), (
        "Acquired? true-branch must route to Set Lock Meta to populate the identity sidecar"
    )


# ---------------------------------------------------------------------------
# Release-side: ownership-checked, with mismatch → StopAndError
# ---------------------------------------------------------------------------


def test_release_input_contract_includes_lock_id() -> None:
    """The lock_release primitive's trigger must accept both `scope` and `lock_id`
    inputs (the lock_id flows through to the ownership check)."""
    primitive = _load_primitive("lock_release")
    trigger = _node(primitive, "Execute Workflow Trigger")
    assert trigger is not None
    inputs = trigger["parameters"]["workflowInputs"]["values"]
    names = {f["name"] for f in inputs}
    assert "scope" in names and "lock_id" in names, (
        f"Trigger must accept scope + lock_id; got {sorted(names)}"
    )


def test_release_has_ownership_check_branches() -> None:
    """The release primitive must have BOTH a delete-on-match path AND a
    StopAndError-on-mismatch path. The ownership check is what makes release
    safe under concurrent contention."""
    primitive = _load_primitive("lock_release")
    has_match_node = _node(primitive, "Match?") is not None
    has_del_counter = any(
        n.get("type") == "n8n-nodes-base.redis" and n["parameters"].get("operation") == "delete"
        for n in primitive.get("nodes", [])
    )
    has_stop_and_error = any(
        n.get("type") == "n8n-nodes-base.stopAndError" for n in primitive.get("nodes", [])
    )
    assert has_match_node, "Release must have a Match? If node for ownership check"
    assert has_del_counter, "Release must have at least one DELETE Redis node"
    assert has_stop_and_error, "Release must have a StopAndError on ownership mismatch"


def test_release_stop_message_uses_logic_error_prefix() -> None:
    """Ownership-mismatch error message must start with 'LOGIC ERROR' (mirrors
    the user's original wording — operators rely on that prefix to distinguish
    bugs from transients)."""
    primitive = _load_primitive("lock_release")
    stop_node = next(n for n in primitive["nodes"] if n["type"] == "n8n-nodes-base.stopAndError")
    msg = stop_node["parameters"]["errorMessage"]
    assert "LOGIC ERROR" in msg, f"StopAndError must use the 'LOGIC ERROR' prefix; got {msg!r}"


# ---------------------------------------------------------------------------
# Error handler: active cleanup with graceful empty-lockScopes path
# ---------------------------------------------------------------------------


def test_error_handler_iterates_lockscopes() -> None:
    """The error handler must reference the `lockScopes` env config (via
    `{{@:env:lockScopes}}` placeholder) and have a per-scope GET → filter → DEL flow."""
    primitive = _load_primitive("error_handler_lock_cleanup")
    prep = _node(primitive, "Prepare Scope List")
    assert prep is not None
    assert "{{@:env:lockScopes}}" in prep["parameters"]["jsCode"], (
        "Error handler must read scopes from env config via {{@:env:lockScopes}} placeholder"
    )
    # Per-scope GET node must exist
    assert _node(primitive, "GET Scope Meta") is not None
    # Filter step must exist
    assert _node(primitive, "Filter Owned Scopes") is not None


def test_error_handler_graceful_empty_scopes() -> None:
    """If lockScopes is empty/missing, the handler must NOT fail — it should
    emit a `cleaned: false` log entry and exit cleanly (per refinement #4)."""
    primitive = _load_primitive("error_handler_lock_cleanup")
    prep = _node(primitive, "Prepare Scope List")
    assert prep is not None
    js = prep["parameters"]["jsCode"]
    assert "no lockScopes registered" in js, (
        "Empty lockScopes path must emit a clear log message identifying the config gap"
    )
    assert "cleanup_terminal" in js, (
        "Empty lockScopes path must set a terminal flag so the If gate skips Redis ops"
    )


# ---------------------------------------------------------------------------
# Namespacing: n8n-lock- and n8n-ratelimit- prefixes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("primitive_key,old_prefix,new_prefix", [
    ("lock_acquisition", "lock-", "n8n-lock-"),
    ("lock_release", "lock-", "n8n-lock-"),
    ("error_handler_lock_cleanup", "lock-", "n8n-lock-"),
    ("rate_limit_check", "ratelimit-", "n8n-ratelimit-"),
])
def test_redis_keys_use_n8n_prefix(primitive_key, old_prefix, new_prefix) -> None:
    """All 4 primitives must use the namespaced `n8n-lock-` / `n8n-ratelimit-`
    prefix — never the bare `lock-` / `ratelimit-` form."""
    text = (PRIMITIVES_DIR / f"{primitive_key}.template.json").read_text()
    # The new prefix MUST be present (proves the primitive was actually updated)
    assert new_prefix in text, (
        f"{primitive_key} must contain the new namespaced prefix {new_prefix!r}"
    )
    # The bare prefix must NOT appear except as part of the new prefix.
    # Use a negative lookahead-equivalent (regex \b<prefix> outside n8n-).
    bare_pattern = re.compile(rf"(?<!n8n-){re.escape(old_prefix)}\$\{{|(?<!n8n-){re.escape(old_prefix)}\\?\$\{{")
    bare_matches = bare_pattern.findall(text)
    assert not bare_matches, (
        f"{primitive_key} still has bare {old_prefix!r} backtick-template usages "
        f"that should be {new_prefix!r}: {bare_matches}"
    )


# ---------------------------------------------------------------------------
# Helper-side: auto-register lockScopes
# ---------------------------------------------------------------------------


def test_auto_register_lock_scopes_for_static_literal(tmp_path: Path) -> None:
    """Running add_lock_to_workflow.py with a static --scope-expression must
    append the resolved scope to <env>.yml.lockScopes idempotently."""
    workspace = tmp_path / "ws"
    init_helper = Path(__file__).resolve().parents[1] / "helpers" / "init.py"
    subprocess.run(
        [sys.executable, str(init_helper), "--workspace", str(workspace)],
        capture_output=True, text=True, check=True,
    )
    # Set up an env yaml + lock primitive stubs.
    (workspace / "n8n-config" / "dev.yml").write_text(yaml.dump({
        "name": "dev", "displayName": "D", "n8n": {"instanceName": "x"},
        "credentials": {}, "workflows": {},
    }))
    (workspace / "n8n-config" / ".env.dev").write_text("N8N_API_KEY=test\n")
    for primitive in ("lock_acquisition", "lock_release"):
        (workspace / "n8n-workflows-template" / f"{primitive}.template.json").write_text(json.dumps({
            "name": primitive, "nodes": [], "connections": {},
        }))
    (workspace / "n8n-workflows-template" / "demo.template.json").write_text(json.dumps({
        "name": "demo",
        "nodes": [{"id": "a", "name": "Webhook", "type": "n8n-nodes-base.webhook",
                   "typeVersion": 2, "position": [240, 300], "parameters": {"path": "demo"}}],
        "connections": {},
        "settings": {"executionOrder": "v1"},
    }))

    helper = Path(__file__).resolve().parents[1] / "helpers" / "add_lock_to_workflow.py"
    # Run twice with the same static scope — should append once, not twice.
    for _ in range(2):
        r = subprocess.run(
            [sys.executable, str(helper),
             "--workspace", str(workspace), "--workflow-key", "demo",
             "--scope-expression", '={{ "my-static-scope" }}'],
            capture_output=True, text=True,
        )
        # First run inserts; second is idempotent — the helper rejects re-adding
        # to the same template, but lockScopes registration runs unconditionally
        # before _insert_lock errors. We're testing lockScopes idempotence, so
        # a non-zero exit on the second run is OK as long as lockScopes is
        # already present from the first run.
        if r.returncode != 0 and "already has" not in r.stderr:
            raise AssertionError(f"Unexpected helper failure: {r.stderr}")

    dev_yaml = yaml.safe_load((workspace / "n8n-config" / "dev.yml").read_text())
    assert dev_yaml.get("lockScopes") == ["my-static-scope"], (
        f"lockScopes must contain the static scope exactly once; got {dev_yaml.get('lockScopes')}"
    )


def test_extract_static_scope_recognizes_canonical_quoted_literal() -> None:
    """The static-scope extractor must recognize `={{ "foo" }}` and `={{ 'foo' }}`
    as static literals."""
    from helpers.add_lock_to_workflow import _extract_static_scope
    assert _extract_static_scope('={{ "foo" }}') == "foo"
    assert _extract_static_scope("={{ 'bar' }}") == "bar"
    assert _extract_static_scope("plain") == "plain"


def test_extract_static_scope_rejects_dynamic_expressions() -> None:
    """Anything containing $json / template-literal interpolation / concat is
    NOT static — extractor must return None so we don't auto-register a noisy
    'lock-' + ... + ... string into lockScopes."""
    from helpers.add_lock_to_workflow import _extract_static_scope
    assert _extract_static_scope("={{ 'foo-' + $json.x }}") is None
    assert _extract_static_scope("={{ `foo-${$json.x}` }}") is None
    assert _extract_static_scope("={{ $execution.id }}") is None


# ---------------------------------------------------------------------------
# Doctor: lock-scopes-unregistered verdict
# ---------------------------------------------------------------------------


def test_doctor_flags_unregistered_lock_scope(tmp_path: Path) -> None:
    """Doctor must WARN when a workflow's Lock Acquire scope literal is missing
    from <env>.yml.lockScopes."""
    workspace = tmp_path / "ws"
    init_helper = Path(__file__).resolve().parents[1] / "helpers" / "init.py"
    subprocess.run(
        [sys.executable, str(init_helper), "--workspace", str(workspace)],
        capture_output=True, text=True, check=True,
    )
    # Env yaml WITHOUT lockScopes, but a workflow template WITH a Lock Acquire node
    # whose scope literal is "missing-scope".
    (workspace / "n8n-config" / "dev.yml").write_text(yaml.dump({
        "name": "dev", "displayName": "D", "n8n": {"instanceName": "x"},
        "credentials": {}, "workflows": {},
    }))
    (workspace / "n8n-config" / ".env.dev").write_text("N8N_API_KEY=test\n")
    (workspace / "n8n-workflows-template" / "locked.template.json").write_text(json.dumps({
        "name": "locked",
        "nodes": [{
            "id": "x", "name": "Lock Acquire", "type": "n8n-nodes-base.executeWorkflow",
            "typeVersion": 1.2, "position": [0, 0],
            "parameters": {"workflowInputs": {"value": {"scope": '={{ "missing-scope" }}'}}},
        }],
        "connections": {},
        "settings": {"executionOrder": "v1"},
    }))

    doctor = Path(__file__).resolve().parents[1] / "helpers" / "doctor.py"
    r = subprocess.run(
        [sys.executable, str(doctor), "--workspace", str(workspace), "--env", "dev", "--json"],
        capture_output=True, text=True,
    )
    out = json.loads(r.stdout)
    labels = " ".join(c["label"] for c in out["checks"])
    assert "lockScopes" in labels, f"Doctor must include a lockScopes check row; got {out}"
    assert out["verdict"] in ("lock-scopes-unregistered", "api-unreachable"), (
        f"Verdict should be lock-scopes-unregistered (or api-unreachable if env "
        f"has no live API); got {out['verdict']}"
    )
