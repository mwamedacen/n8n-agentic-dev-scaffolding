"""n8n control via REST + MCP. Read, edit, extend — this file is yours."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Local imports of admin happen lazily inside helpers so `--help` / `--version`
# don't pay the import cost. But for `from helpers import *` we need the public
# surface visible.
from admin import (
    REPO_ROOT,
    _load_env,
    _yaml_for,
    default_env,
    ensure_client,
    list_envs,
    write_debug_artifact,
)

# Ensure n8n/build_scripts, n8n/resync_scripts, n8n/deployment_scripts are
# importable. Idempotent — safe to evaluate this module multiple times.
_BUILD_DIR = REPO_ROOT / "n8n" / "build_scripts"
_RESYNC_DIR = REPO_ROOT / "n8n" / "resync_scripts"
_DEPLOY_DIR = REPO_ROOT / "n8n" / "deployment_scripts"
for _d in (_BUILD_DIR, _RESYNC_DIR, _DEPLOY_DIR):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))


# ---------------------------------------------------------------------------
# Demo-suite canonical constants (plan §3a/§4b)
# ---------------------------------------------------------------------------

# Used by every DoD that needs a "known-safe target" — see plan §3a. The
# leading underscore signals "module-private" by Python convention BUT is
# explicitly re-exported via __all__ below so `from helpers import *`
# (which `n8n-harness -c` uses) picks it up.
_TEST_WORKFLOW_KEY = "demo_smoke"
TEST_WORKFLOW_KEY = _TEST_WORKFLOW_KEY  # Public alias for star-import.

# Demos with a programmatically-runnable trigger (Webhook). plan-level §5
# requires every one of these to deploy → run → status == "success".
RUNNABLE_DEMOS: List[str] = [
    "demo_smoke",
    "demo_branching",
    "demo_batch_processor",
    "demo_subworkflow_caller",
    "demo_external_js_code",
    "demo_http_call",
    "demo_ai_summary",
    "demo_scheduled_report",
    "demo_chat_assistant",  # Chat trigger + Webhook (manual run) → runnable
]

# Demos whose trigger is intrinsically structural — they cannot be invoked via
# webhook and verify only via deploy + GET /workflows/{id}. See plan §5
# carve-out and §6 for the reasoning.
STRUCTURAL_ONLY_DEMOS: Dict[str, str] = {
    "demo_subworkflow_callee": "Execute Workflow Trigger callee — fires only when invoked from a parent",
    "demo_error_handler": "Error Trigger — fires only on another workflow's failure",
    "demo_locked_pipeline": "References lock_acquiring/releasing sub-workflows that need real Redis credentials",
    "demo_integrations_showcase": "Microsoft 365 + Gmail + Redis nodes need real credentials to execute",
}


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------

def _env(env: Optional[str]) -> str:
    return env or default_env()


def _yaml_workflows(env: str) -> Dict[str, Dict[str, Any]]:
    cfg = _yaml_for(env)
    return cfg.get("workflows") or {}


def list_workflows(env: Optional[str] = None) -> List[Dict[str, Any]]:
    """Live workflows from n8n joined with YAML keys.

    Returns [{key, id, active, name}] for each. Workflows the API surfaces
    that YAML doesn't know yet appear with `key=None` (tolerant join).
    """
    env_name = _env(env)
    client = ensure_client(env_name)
    by_id_to_key: Dict[str, str] = {
        str((wf or {}).get("id", "")): k
        for k, wf in _yaml_workflows(env_name).items()
        if (wf or {}).get("id")
    }
    out: List[Dict[str, Any]] = []
    cursor = None
    while True:
        params: Dict[str, Any] = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        r = client.get("/api/v1/workflows", params=params)
        r.raise_for_status()
        data = r.json()
        for w in data.get("data", []):
            wid = str(w.get("id", ""))
            out.append({
                "key": by_id_to_key.get(wid),
                "id": wid,
                "active": bool(w.get("active", False)),
                "name": w.get("name"),
            })
        cursor = data.get("nextCursor")
        if not cursor:
            break
    return out


def get_workflow(key: str, env: Optional[str] = None) -> Dict[str, Any]:
    """Fetch live workflow JSON by key (looks up id from YAML)."""
    env_name = _env(env)
    workflows = _yaml_workflows(env_name)
    if key not in workflows:
        raise KeyError(
            f"workflow key '{key}' not in n8n/environments/{env_name}.yaml. "
            f"Known: {sorted(workflows.keys())}"
        )
    wf_id = str((workflows[key] or {}).get("id", "")).strip()
    if not wf_id or wf_id.startswith("your-"):
        raise RuntimeError(
            f"workflow '{key}' has placeholder id in YAML; run `bootstrap_workflows.py {env_name}` first."
        )
    client = ensure_client(env_name)
    r = client.get(f"/api/v1/workflows/{wf_id}")
    r.raise_for_status()
    return r.json()


def read_template(key: str) -> str:
    """Filesystem read of n8n/workflows/<key>.template.json (raw text)."""
    p = REPO_ROOT / "n8n" / "workflows" / f"{key}.template.json"
    if not p.exists():
        raise FileNotFoundError(f"template not found: {p}")
    return p.read_text()


def hydrate(key: str, env: Optional[str] = None) -> str:
    """Hydrate a template into n8n/workflows/generated/<env>/<key>.generated.json.

    Calls `n8n/build_scripts/hydrate_workflow.hydrate_workflow()` directly (not
    `main()`, which would `argparse + sys.exit()`). Returns the absolute path
    of the generated file.
    """
    env_name = _env(env)
    template_path = REPO_ROOT / "n8n" / "workflows" / f"{key}.template.json"
    if not template_path.exists():
        raise FileNotFoundError(f"template not found: {template_path}")
    output_dir = REPO_ROOT / "n8n" / "workflows" / "generated" / env_name

    from env_config import load_env_config  # type: ignore
    from hydrate_workflow import hydrate_workflow  # type: ignore

    env_config = load_env_config(env_name)
    out = hydrate_workflow(
        template_path=template_path,
        workflow_key=key,
        env_config=env_config,
        base_dir=REPO_ROOT,
        output_dir=output_dir,
    )
    return str(out)


# ---------------------------------------------------------------------------
# Phase 1b additions — full helper surface
# ---------------------------------------------------------------------------

def read_template_generated(key: str, env: Optional[str] = None) -> str:
    """Read the hydrated template from n8n/workflows/generated/<env>/<key>.generated.json."""
    env_name = _env(env)
    p = REPO_ROOT / "n8n" / "workflows" / "generated" / env_name / f"{key}.generated.json"
    if not p.exists():
        raise FileNotFoundError(f"generated workflow not found: {p}; run hydrate('{key}', env='{env_name}') first")
    return p.read_text()


def deploy(key: str, env: Optional[str] = None, activate: bool = True, rehydrate: bool = False) -> Dict[str, Any]:
    """Deploy a workflow to n8n.

    By default uses the existing `n8n/workflows/generated/<env>/<key>.generated.json`
    as-is — call `hydrate(key)` first if it doesn't exist yet. This default keeps
    `hydrate → deploy → diff` round-trips byte-stable; opt into `rehydrate=True`
    when you specifically want fresh UUIDs minted at deploy time.
    """
    env_name = _env(env)
    workflows = _yaml_workflows(env_name)
    if key not in workflows:
        raise KeyError(f"workflow key '{key}' not in {env_name}.yaml")
    wf_id = str((workflows[key] or {}).get("id", "")).strip()
    if not wf_id or wf_id.startswith("your-"):
        raise RuntimeError(f"workflow '{key}' has placeholder id; run bootstrap first")

    gen_path = REPO_ROOT / "n8n" / "workflows" / "generated" / env_name / f"{key}.generated.json"
    if rehydrate or not gen_path.exists():
        gen_path = Path(hydrate(key, env=env_name))
    payload = json.loads(gen_path.read_text())

    # n8n PUT /workflows/{id} expects only certain fields.
    body = {
        "name": payload.get("name"),
        "nodes": payload.get("nodes", []),
        "connections": payload.get("connections", {}),
        "settings": payload.get("settings") or {"executionOrder": "v1"},
    }
    if "staticData" in payload:
        body["staticData"] = payload["staticData"]

    client = ensure_client(env_name)
    debug_on = os.environ.get("N8H_DEBUG_DEPLOYS") == "1"
    record: Dict[str, Any] = {
        "env": env_name,
        "key": key,
        "workflow_id": wf_id,
        "activate": activate,
    }
    if debug_on:
        record["pre_hydration"] = read_template(key)
        record["post_hydration"] = body
        record["api_request"] = {
            "method": "PUT",
            "url": f"{client.base_url}/api/v1/workflows/{wf_id}",
            "headers": dict(client._session.headers),
            "body": body,
        }
    r = client.put(f"/api/v1/workflows/{wf_id}", json=body)
    if debug_on:
        record["api_response"] = {
            "status": r.status_code,
            "body": _safe_json(r),
        }
        write_debug_artifact(record)
    if r.status_code >= 300:
        raise RuntimeError(f"PUT /workflows/{wf_id} → HTTP {r.status_code}: {r.text}")
    out = r.json()
    if activate:
        ar = client.post(f"/api/v1/workflows/{wf_id}/activate")
        if ar.status_code >= 300:
            raise RuntimeError(f"activate → HTTP {ar.status_code}: {ar.text}")
        out["active"] = True
    return out


def deactivate(key: str, env: Optional[str] = None) -> Dict[str, Any]:
    env_name = _env(env)
    wf_id = str((_yaml_workflows(env_name).get(key) or {}).get("id", ""))
    if not wf_id:
        raise KeyError(f"workflow key '{key}' not in {env_name}.yaml")
    client = ensure_client(env_name)
    r = client.post(f"/api/v1/workflows/{wf_id}/deactivate")
    if r.status_code >= 300:
        raise RuntimeError(f"deactivate → HTTP {r.status_code}: {r.text}")
    return r.json()


def bootstrap(env: Optional[str] = None, dry_run: bool = False) -> int:
    """Mint empty placeholder workflows in n8n for every YAML key with a placeholder id.

    Imports `bootstrap_workflows.bootstrap_env` directly (sys.path setup at
    module top); no subprocess. Returns the same 0/1 exit code the CLI does.
    """
    env_name = _env(env)
    from bootstrap_workflows import bootstrap_env  # type: ignore
    return bootstrap_env(env_name, dry_run=dry_run)


def resync(key: str, env: Optional[str] = None) -> str:
    """Fetch live workflow, dehydrate, write back to template. Returns template path."""
    env_name = _env(env)
    from dehydrate_workflow import dehydrate_workflow  # type: ignore  (sys.path setup at module top)
    workflow = get_workflow(key, env=env_name)
    template_path = REPO_ROOT / "n8n" / "workflows" / f"{key}.template.json"
    dehydrated = dehydrate_workflow(
        workflow=workflow,
        env_name=env_name,
        base_dir=REPO_ROOT,
        output_path=template_path,
        remove_triggers=False,
    )
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text(json.dumps(dehydrated, indent=2) + "\n")
    return str(template_path)


def dehydrate(json_text: str, env: Optional[str] = None) -> str:
    """Dehydrate a raw workflow JSON (string in, string out)."""
    env_name = _env(env)
    from dehydrate_workflow import dehydrate_workflow  # type: ignore  (sys.path setup at module top)
    workflow = json.loads(json_text)
    out = dehydrate_workflow(
        workflow=workflow,
        env_name=env_name,
        base_dir=REPO_ROOT,
        output_path=REPO_ROOT / "n8n" / "workflows" / "_dehydrate_tmp.json",
        remove_triggers=False,
    )
    return json.dumps(out, indent=2)


def run_workflow(key: str, env: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Trigger a workflow run.

    n8n's public REST API does NOT expose a "run-this-workflow" endpoint
    (`POST /workflows/{id}/run` returns 405). The agent-facing pattern that
    actually works on a hosted instance is:

      1. Authoring side: every demo workflow uses a Webhook trigger.
      2. We pull the live workflow JSON, find the Webhook node's `path`, and
         POST to `<base>/webhook/<path>` (active) or `<base>/webhook-test/<path>`.
      3. We poll `/executions?workflowId=<id>` to find the resulting execution
         and return the most recent one.

    For workflows without a webhook trigger, we raise a clear error rather than
    pretending the API call worked.
    """
    import time as _time
    env_name = _env(env)
    wf_id = str((_yaml_workflows(env_name).get(key) or {}).get("id", ""))
    if not wf_id:
        raise KeyError(f"workflow key '{key}' not in {env_name}.yaml")
    client = ensure_client(env_name)
    live = client.get(f"/api/v1/workflows/{wf_id}")
    live.raise_for_status()
    live_wf = live.json()

    webhook_node = next(
        (n for n in live_wf.get("nodes", []) if n.get("type") == "n8n-nodes-base.webhook"),
        None,
    )
    if webhook_node is None:
        # Fall back to attempting the (typically unsupported) public-API run,
        # so the error surface is honest and includes the original failure.
        r = client.post(f"/api/v1/workflows/{wf_id}/run", json=(payload or {}))
        if r.status_code >= 300:
            raise RuntimeError(
                f"workflow '{key}' has no Webhook trigger and n8n's public REST API "
                f"does not support /workflows/{{id}}/run (HTTP {r.status_code}). "
                f"Add a webhook trigger to make it agent-runnable."
            )
        return r.json()

    path = (webhook_node.get("parameters") or {}).get("path", "")
    method = ((webhook_node.get("parameters") or {}).get("httpMethod") or "POST").upper()
    if not path:
        raise RuntimeError(f"workflow '{key}' webhook has no path field")

    before = _time.time()
    # Try active webhook first; fall back to test webhook (n8n cloud uses both).
    base = client.base_url
    body = payload or {"trigger": "n8n-harness"}
    import requests as _req
    last_resp = None
    for url in (f"{base}/webhook/{path}", f"{base}/webhook-test/{path}"):
        try:
            r = _req.request(method, url, json=body, timeout=30)
        except Exception as e:
            last_resp = (url, "exception", str(e))
            continue
        if r.status_code < 300:
            last_resp = (url, r.status_code, r.text[:200])
            break
        last_resp = (url, r.status_code, r.text[:200])
    if last_resp and isinstance(last_resp[1], int) and last_resp[1] >= 300:
        raise RuntimeError(f"webhook trigger failed: {last_resp}")

    # Poll /executions to find the one this trigger created.
    # 30s matches plan §3a/§5 (wait_for_execution default).
    deadline = _time.time() + 30
    while _time.time() < deadline:
        ex = client.get("/api/v1/executions", params={"workflowId": wf_id, "limit": 5})
        ex.raise_for_status()
        items = ex.json().get("data", [])
        for item in items:
            started_str = item.get("startedAt") or ""
            if started_str:
                from datetime import datetime
                started = datetime.fromisoformat(started_str.replace("Z", "+00:00")).timestamp()
                if started >= before - 2.0:
                    return item
        _time.sleep(0.5)
    raise RuntimeError(f"webhook posted ok but no matching execution found within 15s for workflow {wf_id}")


def get_execution(execution_id: str | int, env: Optional[str] = None) -> Dict[str, Any]:
    env_name = _env(env)
    client = ensure_client(env_name)
    r = client.get(f"/api/v1/executions/{execution_id}", params={"includeData": "true"})
    if r.status_code >= 300:
        raise RuntimeError(f"GET execution → HTTP {r.status_code}: {r.text}")
    return r.json()


_TERMINAL_FAILURE_STATUSES = {"error", "crashed", "canceled", "failed"}


def wait_for_execution(execution_id: str | int, timeout: int = 30, env: Optional[str] = None) -> Dict[str, Any]:
    """Poll get_execution until terminal, asserts status == 'success'.

    Per plan §3a: never accept `running` / `waiting` as terminal — a forever-stuck
    workflow MUST raise. Terminal conditions:
      - finished == true AND status == "success" → return the dict
      - finished == true AND status != "success" → raise RuntimeError
      - status in {"error", "crashed", "canceled", "failed"} (even with
        finished == false; n8n cloud sometimes leaves finished=false for a
        while after status flips to "error") → raise RuntimeError
      - timeout exceeded → raise TimeoutError
    """
    import time as _time
    env_name = _env(env)
    deadline = _time.time() + timeout
    last: Dict[str, Any] = {}
    while _time.time() < deadline:
        last = get_execution(execution_id, env=env_name)
        status = last.get("status")
        if last.get("finished") is True:
            if status == "success":
                return last
            raise RuntimeError(
                f"execution {execution_id} finished with non-success status "
                f"{status!r}; full execution: {last}"
            )
        if status in _TERMINAL_FAILURE_STATUSES:
            raise RuntimeError(
                f"execution {execution_id} reached terminal failure status "
                f"{status!r} (n8n hasn't flipped finished=true yet, but it won't recover)"
            )
        _time.sleep(1.0)
    raise TimeoutError(
        f"execution {execution_id} did not finish within {timeout}s "
        f"(last status: {last.get('status')!r}, finished={last.get('finished')!r})"
    )


def validate_workflow_json(json_text: str) -> Dict[str, Any]:
    """Validate a workflow JSON via n8n-mcp `validate_workflow` if available, else REST-fallback structural check.

    Returns: {valid: bool, errors: list[str], validator_used: 'n8n-mcp' | 'rest-fallback'}
    """
    if os.environ.get("_FORCE_REST_VALIDATOR") == "1":
        return _rest_fallback_validator(json_text)

    # Try MCP — only available when running inside an MCP-registered Claude session.
    try:
        wf = json.loads(json_text)
    except json.JSONDecodeError as e:
        return {"valid": False, "errors": [f"invalid JSON: {e}"], "validator_used": "rest-fallback"}

    mcp = _try_mcp_validate(wf)
    if mcp is not None:
        return {**mcp, "validator_used": "n8n-mcp"}

    # Fallback
    return _rest_fallback_validator(json_text)


def _try_mcp_validate(workflow: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Best-effort MCP validate; always returns None from inside this module.

    Known limitation (plan §6 deviation #16): n8n-mcp is mediated by the agent's
    runtime (Claude Code, Codex), not by a network-reachable RPC the helper
    module can dial. When `n8n-harness -c "..."` runs the snippet, the snippet
    is in a separate Python process from the agent loop, so we cannot reach
    `mcp__n8n-mcp__validate_workflow` from here.

    The agent has two recourses:
      1. Call the MCP tool directly themselves (recommended for new workflow
         authoring) — `mcp__n8n-mcp__validate_workflow` accepts the JSON.
      2. Use this helper for the structural REST-fallback check, which is
         what `validate_workflow_json` actually runs.

    If a future implementation routes MCP through a local socket / sidecar,
    replace this stub.
    """
    return None


def _rest_fallback_validator(json_text: str) -> Dict[str, Any]:
    """Structural check: top-level nodes/connections present, every node has name/type/parameters."""
    errors: List[str] = []
    try:
        wf = json.loads(json_text)
    except json.JSONDecodeError as e:
        return {"valid": False, "errors": [f"invalid JSON: {e}"], "validator_used": "rest-fallback"}
    if not isinstance(wf, dict):
        return {"valid": False, "errors": ["top-level not an object"], "validator_used": "rest-fallback"}
    if "nodes" not in wf or not isinstance(wf["nodes"], list):
        errors.append("missing top-level 'nodes' array")
    if "connections" not in wf or not isinstance(wf.get("connections", {}), dict):
        errors.append("missing top-level 'connections' object")
    for i, node in enumerate(wf.get("nodes", []) or []):
        if not isinstance(node, dict):
            errors.append(f"nodes[{i}]: not an object")
            continue
        for fld in ("name", "type", "parameters"):
            if fld not in node:
                errors.append(f"nodes[{i}] ({node.get('name', '?')}): missing '{fld}'")
    return {"valid": not errors, "errors": errors, "validator_used": "rest-fallback"}


def cloud_fn(name: str, env: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
    """POST to local/Railway cloud_functions/ service: `<apiUrl>/<name>` with kwargs as JSON body."""
    env_name = _env(env)
    cfg = _yaml_for(env_name)
    base = (cfg.get("cloudFunction") or {}).get("apiUrl", "").rstrip("/")
    if not base:
        base = "http://localhost:8000"
    import requests as _req
    r = _req.post(f"{base}/{name}", json=kwargs, timeout=60)
    if r.status_code >= 300:
        raise RuntimeError(f"cloud_fn {name} → HTTP {r.status_code}: {r.text}")
    return r.json() if r.headers.get("Content-Type", "").startswith("application/json") else {"text": r.text}


def llm(prompt: str, model: Optional[str] = None, **kwargs: Any) -> str:
    """Single-turn LLM call via OpenRouter. Defaults to a cheap text model."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY missing in environment")
    model = model or "openai/gpt-4o-mini"
    import requests as _req
    r = _req.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.pop("temperature", 0),
            **kwargs,
        },
        timeout=60,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"llm → HTTP {r.status_code}: {r.text}")
    return r.json()["choices"][0]["message"]["content"]


def http_get(url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 20.0) -> str:
    """Plain stdlib urllib.request — no proxy fallback (no Browser-Use-equivalent)."""
    import urllib.request, gzip
    h = {"User-Agent": "n8n-harness/0.1.0", "Accept-Encoding": "gzip"}
    if headers:
        h.update(headers)
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as resp:
        data = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return data.decode()


# ---------------------------------------------------------------------------
# semantic diff
# ---------------------------------------------------------------------------

# Keys to ignore in workflow_semantic_diff. The first group is the literal
# plan §3a list; the second is additions discovered during implementation
# (see plan §6 deviation #15 for rationale). Removing any of these from the
# ignore list would make every resync round-trip diff non-empty.
_DIFF_IGNORE = {
    # Plan §3a literal:
    "id",                  # per-instance workflow GUID
    "versionId",           # changes on every save
    "updatedAt",           # volatile timestamp
    "createdAt",           # volatile timestamp
    "active",              # controlled by deploy(activate=...), not authored
    "webhookId",           # minted per-env via {{HYDRATE:uuid:...}}
    "triggerId",           # ditto
    "pinData",             # UI-only debug data — never templated
    "tags",                # per-instance taxonomy
    # Implementation additions (cloud / per-tenant / runtime state):
    "shared",              # n8n-cloud sharing scopes
    "homeProject",         # n8n-cloud project ownership
    "usedCredentials",     # cloud-side resolved credential refs
    "isArchived",          # cloud archive state
    "staticData",          # workflow-static execution state
    "activeVersion",       # cloud version pointer
    "activeVersionId",     # cloud version pointer
    "description",         # cloud-only field; templates lack this
    "triggerCount",        # cloud-computed metric
    "versionCounter",      # cloud-computed
    "scopes",              # cloud-computed
    "parentFolder",        # cloud-computed
}
# `meta` sub-keys ignored for the same reason: n8n-cloud sets these on import.
_META_IGNORE = {"templateCredsSetupCompleted", "templateId", "instanceId"}


def workflow_semantic_diff(local: Dict[str, Any], live: Dict[str, Any]) -> List[str]:
    """Compare two workflow JSONs ignoring volatile metadata.

    Ignore-list (from §3a): id, versionId, updatedAt, createdAt, active, webhookId,
    triggerId, pinData, meta.templateCredsSetupCompleted, meta.templateId, tags,
    plus position values rounded to nearest int.

    Returns a list of human-readable diff strings (empty == identical).
    """
    return _diff(_canon(local), _canon(live), path="")


def _canon(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in _DIFF_IGNORE:
                continue
            if k == "meta":
                if isinstance(v, dict):
                    canon_meta = {mk: _canon(mv) for mk, mv in v.items() if mk not in _META_IGNORE}
                    if canon_meta:
                        out[k] = canon_meta
                # else: drop meta entirely (None == {} == missing)
                continue
            if k == "position" and isinstance(v, list):
                out[k] = [round(float(x)) for x in v]
            else:
                out[k] = _canon(v)
        return out
    if isinstance(obj, list):
        return [_canon(x) for x in obj]
    return obj


def _diff(a: Any, b: Any, path: str) -> List[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out: List[str] = []
        for k in sorted(set(a) | set(b)):
            sub = f"{path}.{k}" if path else k
            if k not in a:
                out.append(f"+{sub}: {b[k]!r}")
            elif k not in b:
                out.append(f"-{sub}: {a[k]!r}")
            else:
                out.extend(_diff(a[k], b[k], sub))
        return out
    if isinstance(a, list) and isinstance(b, list):
        out: List[str] = []
        if len(a) != len(b):
            out.append(f"~{path}: len {len(a)} != {len(b)}")
        for i in range(min(len(a), len(b))):
            out.extend(_diff(a[i], b[i], f"{path}[{i}]"))
        return out
    if a != b:
        return [f"~{path}: {a!r} != {b!r}"]
    return []


# ---------------------------------------------------------------------------
# attach / detach (Phase 3)
# ---------------------------------------------------------------------------

def attach(env_name: str, base_url: str, api_key: str, **kwargs: Any) -> Dict[str, Any]:
    """Attach an ephemeral environment without editing root .env.

    Writes:
      - n8n/environments/attached.<env_name>.yaml (minimal config)
      - .env.attached.<env_name> (secrets — gitignored via the glob added in Phase 1a step 8)

    Then verifies by hitting GET /api/v1/workflows on the new env.
    """
    if not env_name or "/" in env_name or env_name.startswith("."):
        raise ValueError(f"invalid env_name: {env_name!r}")

    yaml_path = REPO_ROOT / "n8n" / "environments" / f"attached.{env_name}.yaml"
    env_path = REPO_ROOT / f".env.attached.{env_name}"

    instance = base_url
    if instance.startswith(("http://", "https://")):
        instance = instance.split("://", 1)[1].rstrip("/")
    yaml_payload = {
        "name": env_name,
        "displayName": kwargs.get("display_name", f"Attached: {env_name}"),
        "workflowNamePostfix": kwargs.get("postfix", f" [ATTACHED-{env_name.upper()}]"),
        "n8n": {"instanceName": instance},
        "workflows": {},
    }
    import yaml as _yaml
    yaml_path.write_text(_yaml.safe_dump(yaml_payload, sort_keys=False))

    env_path.write_text(
        f"N8N_INSTANCE_NAME={instance}\n"
        f"N8N_API_KEY={api_key}\n"
    )
    try:
        os.chmod(env_path, 0o600)
    except OSError:
        pass

    # Validate
    client = ensure_client(env_name)
    r = client.get("/api/v1/workflows", params={"limit": 1})
    if r.status_code != 200:
        # roll back the files we wrote
        env_path.unlink(missing_ok=True)
        yaml_path.unlink(missing_ok=True)
        raise RuntimeError(f"attach validation failed: HTTP {r.status_code}: {r.text[:200]}")
    return {"env": env_name, "base_url": base_url, "verified": True}


def detach(env_name: str) -> Dict[str, Any]:
    """Remove the attached env's YAML and .env.attached.* files. Idempotent."""
    yaml_path = REPO_ROOT / "n8n" / "environments" / f"attached.{env_name}.yaml"
    env_path = REPO_ROOT / f".env.attached.{env_name}"
    removed = []
    for p in (yaml_path, env_path):
        if p.exists():
            p.unlink()
            removed.append(str(p.relative_to(REPO_ROOT)))
    # Drop the cached client for this env
    from admin import restart_client as _restart
    _restart(env_name)
    return {"env": env_name, "removed": removed}


# ---------------------------------------------------------------------------
# Docker-based local n8n provisioning (Phase 3, optional)
# ---------------------------------------------------------------------------

def start_local_n8n(env_name: str = "local", port: int = 5678) -> Dict[str, Any]:
    """Start a local n8n container. Idempotent. Prints live URL.

    Token minting cannot be fully automated — n8n's owner-account creation is
    a UI flow on first run. v1 prints the URL; the user creates the API key,
    then calls attach() with it.
    """
    import subprocess
    import shutil
    if not shutil.which("docker"):
        raise RuntimeError("docker not on PATH; install Docker Desktop or skip start_local_n8n")
    name = f"n8n-harness-{env_name}"
    # Idempotent: if already running, just return.
    ps = subprocess.run(
        ["docker", "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        capture_output=True, text=True,
    )
    url = f"http://localhost:{port}"
    if ps.stdout.strip() == name:
        print(f"{name} already running at {url}")
        return {"name": name, "url": url, "started": False}
    # Start
    r = subprocess.run(
        [
            "docker", "run", "-d", "--rm",
            "--name", name,
            "-p", f"{port}:5678",
            "-e", "N8N_HOST=localhost",
            "-e", f"N8N_PORT={port}",
            "n8nio/n8n:latest",
        ],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"docker run failed: {r.stderr.strip()}")
    print(f"started {name} at {url}")
    print(f"open {url} to create the owner account, then mint an API key in Settings > API.")
    print(f"after, call: n8n-harness -c 'attach({env_name!r}, base_url={url!r}, api_key=\"...\")'")
    return {"name": name, "url": url, "started": True}


def stop_local_n8n(env_name: str = "local") -> Dict[str, Any]:
    """Stop the n8n-harness Docker container for env_name. Idempotent."""
    import subprocess
    import shutil
    if not shutil.which("docker"):
        return {"name": f"n8n-harness-{env_name}", "stopped": False, "reason": "docker not on PATH"}
    name = f"n8n-harness-{env_name}"
    r = subprocess.run(["docker", "stop", name], capture_output=True, text=True)
    return {"name": name, "stopped": r.returncode == 0, "stderr": r.stderr.strip()[:200]}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _safe_json(resp: Any) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text


def find_skills_by_topic(topic: str) -> List[str]:
    """Grep pattern-skills/*.md for `topic`. Returns relative paths."""
    skills_dir = REPO_ROOT / "pattern-skills"
    if not skills_dir.exists():
        return []
    out = []
    needle = topic.lower()
    for p in sorted(skills_dir.glob("*.md")):
        try:
            text = p.read_text().lower()
        except Exception:
            continue
        if needle in p.stem.lower() or needle in text:
            out.append(str(p.relative_to(REPO_ROOT)))
    return out


# Phase 2 hook (declared here so `from helpers import *` exposes it once §2 lands).
NODE_TYPE_TO_SERVICE: Dict[str, str] = {
    "n8n-nodes-base.microsoftExcel": "microsoft-365",
    "n8n-nodes-base.microsoftOutlook": "microsoft-365",
    "n8n-nodes-base.microsoftTeams": "microsoft-365",
    "n8n-nodes-base.microsoftSharepoint": "microsoft-365",
    "n8n-nodes-base.microsoftOneDrive": "microsoft-365",
    "n8n-nodes-base.gmail": "gmail",
    "n8n-nodes-base.gmailTrigger": "gmail",
    "n8n-nodes-base.redis": "redis",
    "n8n-nodes-base.googleDrive": "google-drive",
    "n8n-nodes-base.googleSheets": "google-drive",
    "n8n-nodes-base.slack": "slack",
    "n8n-nodes-base.notion": "notion",
    "n8n-nodes-base.airtable": "airtable",
    "n8n-nodes-base.webhook": "webhooks",
    "n8n-nodes-base.respondToWebhook": "webhooks",
}


_PATTERN_TRIGGERS: Dict[str, List[str]] = {
    # pattern-skill-stem -> node types whose presence triggers it
    "subworkflows": ["n8n-nodes-base.executeWorkflow", "n8n-nodes-base.executeWorkflowTrigger"],
    "error-handling": ["n8n-nodes-base.errorTrigger"],
    "credential-refs": [],  # always relevant when ANY service is involved
    "multi-env-uuid-collision": [
        "n8n-nodes-base.webhook", "n8n-nodes-base.scheduleTrigger",
        "n8n-nodes-base.manualTrigger", "@n8n/n8n-nodes-langchain.chatTrigger",
    ],
    "mcp-validate-deploy": [],  # always relevant
    "llm-providers": [
        "n8n-nodes-base.httpRequest",  # often used to call OpenRouter
        "@n8n/n8n-nodes-langchain.lmChatOpenAi",
        "@n8n/n8n-nodes-langchain.lmChatOpenRouter",
        "@n8n/n8n-nodes-langchain.outputParserStructured",
    ],
}
_ALWAYS_ON_PATTERNS = {"credential-refs", "mcp-validate-deploy"}


def find_skills(workflow_key: str, env: Optional[str] = None, max_results: int = 10) -> List[str]:
    """Return matching pattern-skills/*.md AND integration-skills/<service>/*.md
    based on a workflow's actual node types. Capped at `max_results`.

    Active call (n8n-harness deviation #11): the agent must call this; there is no
    passive-on-navigate equivalent.

    Source preference: live workflow first (so a UI-edit since the last resync is
    reflected), template fallback if the workflow isn't deployed yet (e.g. during
    initial authoring before bootstrap).

    Selection rules:
      - integration-skills/<service>/*.md included if ANY node maps to <service>
        via NODE_TYPE_TO_SERVICE.
      - pattern-skills/*.md included if its trigger-node-type list overlaps the
        workflow's nodes; or if it is in _ALWAYS_ON_PATTERNS (validate, credentials).
    """
    env_name = _env(env)
    wf: Optional[Dict[str, Any]] = None
    # Prefer live workflow (catches UI edits since last resync).
    try:
        wf = get_workflow(workflow_key, env=env_name)
    except Exception:
        wf = None
    # Fall back to local template (covers pre-deploy authoring).
    if wf is None:
        template_path = REPO_ROOT / "n8n" / "workflows" / f"{workflow_key}.template.json"
        if not template_path.exists():
            return []
        try:
            wf = json.loads(template_path.read_text())
        except Exception:
            return []
    services = set()
    node_types = set()
    for node in wf.get("nodes", []) or []:
        t = node.get("type", "")
        node_types.add(t)
        svc = NODE_TYPE_TO_SERVICE.get(t)
        if svc:
            services.add(svc)
    out: List[str] = []
    pattern_dir = REPO_ROOT / "pattern-skills"
    if pattern_dir.exists():
        for p in sorted(pattern_dir.glob("*.md")):
            stem = p.stem
            triggers = _PATTERN_TRIGGERS.get(stem, [])
            if stem in _ALWAYS_ON_PATTERNS or any(t in node_types for t in triggers):
                out.append(str(p.relative_to(REPO_ROOT)))
    integ_dir = REPO_ROOT / "integration-skills"
    for svc in sorted(services):
        sd = integ_dir / svc
        if sd.exists():
            for p in sorted(sd.glob("*.md")):
                out.append(str(p.relative_to(REPO_ROOT)))
    return out[:max_results]


def _suite_coverage() -> Dict[str, Any]:
    """Coverage matrix for the demo_* suite (§4b). Used by Phase 2 DoD #9.

    Returns a dict with both the per-target counts and a `_meta` block
    breaking out runnable vs structural-only demos honestly.
    """
    targets: Dict[str, int] = {
        "trigger_schedule": 0, "trigger_webhook": 0, "trigger_manual": 0,
        "trigger_chat": 0, "trigger_error": 0,
        "control_if": 0, "control_switch": 0, "control_merge": 0, "control_split_in_batches": 0,
        "subworkflow": 0, "locking": 0,
        "code_inline": 0, "code_external_js": 0,
        "ai_structured": 0, "http_cloud_fn": 0,
        "integration_microsoft365": 0, "integration_gmail": 0, "integration_redis": 0,
        "placeholder_env": 0, "placeholder_txt": 0, "placeholder_json": 0,
        "placeholder_html": 0, "placeholder_js": 0, "placeholder_uuid": 0,
    }
    type_to_target = {
        "n8n-nodes-base.scheduleTrigger": "trigger_schedule",
        "n8n-nodes-base.webhook": "trigger_webhook",
        "n8n-nodes-base.manualTrigger": "trigger_manual",
        "@n8n/n8n-nodes-langchain.chatTrigger": "trigger_chat",
        "n8n-nodes-base.errorTrigger": "trigger_error",
        "n8n-nodes-base.if": "control_if",
        "n8n-nodes-base.switch": "control_switch",
        "n8n-nodes-base.merge": "control_merge",
        "n8n-nodes-base.splitInBatches": "control_split_in_batches",
        "n8n-nodes-base.executeWorkflow": "subworkflow",
        "n8n-nodes-base.code": "code_inline",
        "n8n-nodes-base.gmail": "integration_gmail",
        "n8n-nodes-base.redis": "integration_redis",
        "n8n-nodes-base.microsoftExcel": "integration_microsoft365",
        "n8n-nodes-base.microsoftSharepoint": "integration_microsoft365",
        "n8n-nodes-base.httpRequest": "http_cloud_fn",
    }
    workflow_dir = REPO_ROOT / "n8n" / "workflows"
    for tpl in sorted(workflow_dir.glob("demo_*.template.json")):
        text = tpl.read_text()
        try:
            wf = json.loads(text)
        except Exception:
            continue
        has_txt = "{{HYDRATE:txt:" in text
        has_json = "{{HYDRATE:json:" in text
        for node in wf.get("nodes", []) or []:
            t = node.get("type", "")
            tgt = type_to_target.get(t)
            if tgt:
                targets[tgt] += 1
            # Locking: Execute Workflow targeting lock_acquiring/releasing
            params = node.get("parameters") or {}
            wid = params.get("workflowId")
            wid_str = str(wid)
            if isinstance(wid, dict):
                wid_str = str(wid.get("value", ""))
            if "lock_acquiring" in wid_str or "lock_releasing" in wid_str:
                targets["locking"] += 1
            # Inline JS code via parameters.jsCode
            if t == "n8n-nodes-base.code":
                code = (params).get("jsCode", "")
                if code and "{{HYDRATE:js:" not in code:
                    targets["code_inline"] += 1
                if "{{HYDRATE:js:" in code:
                    targets["code_external_js"] += 1
            # AI structured output (LangChain or txt+json placeholders together)
            if "lmChatOpenRouter" in t or "openRouter" in t.lower() or "outputParserStructured" in t:
                targets["ai_structured"] += 1
        # Treat presence of both txt+json placeholders in same workflow as ai_structured proof
        if has_txt and has_json:
            targets["ai_structured"] += 1
        # Placeholder-type tally on raw text (covers any nesting depth).
        for ph_type in ("env", "txt", "json", "html", "js", "uuid"):
            if f"{{{{HYDRATE:{ph_type}:" in text:
                targets[f"placeholder_{ph_type}"] += 1
    # Honest accounting of which demos can be programmatically invoked.
    workflow_dir = REPO_ROOT / "n8n" / "workflows"
    found_demos = sorted(p.stem.replace(".template", "") for p in workflow_dir.glob("demo_*.template.json"))
    runnable = [d for d in found_demos if d in RUNNABLE_DEMOS]
    structural = [d for d in found_demos if d in STRUCTURAL_ONLY_DEMOS]
    other = [d for d in found_demos if d not in RUNNABLE_DEMOS and d not in STRUCTURAL_ONLY_DEMOS]
    targets["_meta"] = {  # type: ignore
        "demos_total": len(found_demos),
        "runnable": runnable,
        "structural_only": structural,
        "uncategorized": other,
    }
    return targets
