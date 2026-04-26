# Validate before deploy

## The canonical loop

```python
hydrate(k := "my_workflow")
r = validate_workflow_json(read_template_generated(k))
assert r["valid"], r["errors"]
deploy(k, activate=True)
ex = run_workflow(k)
result = wait_for_execution(ex["id"], timeout=30)
assert result["finished"] and result["status"] == "success", result
```

Five steps, four assertions. Skipping any of them and you're flying blind.

## What each step catches

| Step | What it catches |
|---|---|
| `hydrate` | Unresolved placeholders, missing files, malformed YAML |
| `validate_workflow_json` | Missing `nodes`/`connections`, broken node shape, bad credentials block |
| `deploy` | API rejects the workflow (HTTP ≥ 300) — usually credential mismatch or invalid expression |
| `run_workflow` | Webhook unreachable (404 = workflow not active, or path mismatch) |
| `wait_for_execution` | Forever-stuck workflow (timeout exceeded), or terminal failure (`status=error`) |

## n8n-mcp vs REST fallback

`validate_workflow_json` tries n8n-mcp's `validate_workflow` first (deeper checks: typeVersion compatibility, node-specific parameter shape). If MCP isn't reachable from the runtime, it falls back to a structural REST check (top-level `nodes`/`connections` present, every node has `name`/`type`/`parameters`).

The return value distinguishes:

```python
r["validator_used"]  # "n8n-mcp" or "rest-fallback"
```

Force REST-fallback for testing:

```bash
_FORCE_REST_VALIDATOR=1 n8n-harness -c "..."
```

## When n8n-mcp's validator catches something REST-fallback misses

n8n-mcp knows each node's exact parameter schema. It catches:

- A `Set` node with `assignments.assignments[i].type` set to a value the node version doesn't support.
- A `Code` node with `language: python` on a node version that's JS-only.
- An `HTTP Request` node with mutually-exclusive auth parameters set.
- Wrong `typeVersion` for the node type.

These slip past REST-fallback because they look structurally correct. **When n8n-mcp is available, use it.** The fallback is for environments where MCP isn't registered (CI, scripted invocations).

## Polling, not "running/waiting accepted"

`wait_for_execution` polls `get_execution(id)` until `finished == true` OR a 30s timeout. It never accepts `running` or `waiting` as terminal — a forever-stuck workflow MUST fail. This is a deliberate plan decision (§3a), to prevent silent-green CI.
