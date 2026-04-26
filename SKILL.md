---
name: n8n-harness
description: Direct n8n control via REST + MCP. Use when the user wants to author, deploy, run, or resync n8n workflows as code. Connects to the user's already-running n8n instance.
---

# n8n-harness

Direct n8n control via REST + MCP. Read `helpers.py` — that's where the functions live. For setup, install, or connection problems, read `install.md`.

## Usage

```bash
n8n-harness -c "
hydrate('demo_smoke')
deploy('demo_smoke', activate=True)
ex = run_workflow('demo_smoke')
print(wait_for_execution(ex['id']))
"
```

- Invoke as `n8n-harness` — it's on `$PATH`. No `cd`, no `uv run`.
- Helpers, `os`, `json`, `sys` are pre-imported in the snippet's scope.
- The N8nClient is cached per (base_url, api_key) and invalidated on `.env` mtime change.

## Tool call shape

```bash
n8n-harness -c '
# any python. helpers pre-imported. no daemon to start.
'
```

Pick the env once with `--env <name>` (or `N8H_ENV=prod`) — defaults to `dev`.

## Default workflow

1. **First edit is the template + YAML, not live n8n UI.** `n8n/workflows/<key>.template.json` is canonical; the live workflow is rendered output.
2. **Always `validate_workflow_json` before `deploy`.** REST-fallback validator catches structural breakage; n8n-mcp's `validate_workflow` (when reachable) catches deeper issues.
3. **After deploy, `run_workflow` then `wait_for_execution` to verify.** No "running" / "waiting" accepted as terminal — a forever-stuck workflow must fail.

```bash
n8n-harness -c '
hydrate(k := "my_workflow")
assert validate_workflow_json(read_template_generated(k))["valid"]
deploy(k, activate=True)
ex = run_workflow(k)
r = wait_for_execution(ex["id"], timeout=30)
assert r["finished"] and r["status"] == "success", r
'
```

## Search first

Search `integration-skills/<service>/` first for the integration you are working with before inventing a new approach.

```bash
n8n-harness -c 'print(find_skills("my_workflow"))'
n8n-harness -c 'print(find_skills_by_topic("subworkflows"))'
```

`find_skills(workflow_key)` is an **active call** — there is no passive-on-navigate analogue in n8n-harness (deliberate deviation from browser-harness's `goto_url`). Call it before authoring; it returns matching `pattern-skills/*.md` plus per-service `integration-skills/<service>/*.md` based on the workflow's actual node `type` fields.

### Available pattern skills

- `pattern-skills/subworkflows.md` — Execute Workflow nodes + tier ordering + ID resolution
- `pattern-skills/error-handling.md` — Error Trigger workflows + lock cleanup pattern
- `pattern-skills/credential-refs.md` — `credentials.<name>.id` placeholder + the credential-`name`-mismatch trap
- `pattern-skills/multi-env-uuid-collision.md` — why each env needs fresh UUIDs
- `pattern-skills/mcp-validate-deploy.md` — the canonical "validate before deploy" loop
- `pattern-skills/llm-providers.md` — OpenRouter and other LLM-provider concerns (not a node-type, so not in `integration-skills/`)

Other patterns (branching, batching, scheduled-triggers, webhook-triggers, chat-trigger, locking, dehydrate-markers, position-recalculation, pindata-hygiene, cloud-functions-call, ai-structured-output, code-node-js) are **agent-authored as you hit them**. The harness gets better only because agents file what they learn.

### Integration-skills (keyed by service, not host)

- `integration-skills/microsoft-365/` — Excel, Outlook, SharePoint, Teams, OneDrive
- `integration-skills/gmail/`
- `integration-skills/redis/`
- `integration-skills/slack/`, `google-drive/`, `notion/`, `airtable/`, `webhooks/` (placeholders — fill in as you learn)

## Always contribute back

If you learned anything non-obvious about how an integration works (a quirky parameter shape, a stable selector, a credential trap), open a PR to `integration-skills/<service>/` before you finish. Default to contributing. The harness gets better only because agents file what they learn.

Examples worth a PR:

- A non-obvious parameter combination that took several attempts to land (e.g. SharePoint's `driveId` vs `siteId`).
- A credential gotcha — the `name` field in YAML must match the credential name in n8n exactly, not just the id.
- A trigger quirk — webhook test URL behavior, schedule timezone surprises.
- A workflow-position rule — n8n does NOT auto-layout, recalculate after node insertion.
- A response-shape detail not in the n8n docs.

### What an integration skill should capture

- Node `type` and stable parameter combinations.
- Credential name/id contract.
- Authentication / scope quirks.
- Common error shapes.
- A 4-line example showing the typical placeholder block.

### Do not write

- Run narration or step-by-step of the specific task you just did.
- Secrets, tokens, credential blobs. `integration-skills/` is shared and public.

## What actually works

- **Hydrate-first deploy.** Edit `*.template.json` + YAML, call `deploy(workflow_key)`. Avoid the "edit live in n8n UI then resync" reflex — templates are canonical.
- **Webhook triggers for runnable demos.** n8n's public REST API does NOT support `/workflows/{id}/run`. `run_workflow()` POSTs to the workflow's webhook path then polls `/executions`. Workflows without a Webhook trigger must be tested in the UI.
- **`workflow_semantic_diff` for round-trip checks.** Ignores `id`, `versionId`, `updatedAt`, `createdAt`, `active`, `webhookId`, `triggerId`, `pinData`, `tags`, `meta.templateCredsSetupCompleted`, `meta.templateId`, plus position values rounded to nearest int. Anything else is a real change.
- **`--debug-deploys` for surgical debugging.** Dumps redacted pre-hydration template, post-hydration JSON, API request, and API response into mode-0600 files under `~/.cache/n8n-harness/debug/<pid>/deploy-<n>.json`. Redaction scrubs `Authorization`, `X-N8N-API-KEY`, `*_API_KEY` / `*_TOKEN` / `*_SECRET` / `*_PASSWORD` keys, and any `credentials.*` blocks before write.
- **`bootstrap()` for fresh envs.** Creates empty placeholder workflows for every key in `n8n/environments/<env>.yaml` that doesn't already have a real ID, and records the n8n-assigned IDs back into the YAML.
- **Compose, don't bulk-helper.** No `deploy_all` / `deactivate_all` / `hydrate_all` / `resync_all` Python helpers. `for k in list_workflows(): deploy(k)` is the loop. Bash scripts (`deploy_all.sh`, etc.) keep their role for non-agent ergonomics.

## Design constraints

- **Templates are canonical, live workflow is rendered output.** First edit is `*.template.json` + YAML, never the n8n UI.
- **MCP `validate_workflow` is a new validation primitive** (no browser-harness equivalent — disclosed in the plan §6 #5). It is *not* analogous to compositor hit-testing. The REST-fallback validator covers it when MCP is unreachable.
- **`run.py` stays tiny.** No argparse, no subcommands, no extra control layer. Manual flag parsing.
- **No manager / retries / config layer.**
- **No `*_all` Python helpers.** Agents compose loops.
- **`integration-skills/` keyed by service, not host.** n8n's stable identifier is *node type* / credential type, so we key by service.
- **No `start_local_n8n` in Phase 1.** browser-harness's free-tier story is funded by the org. We don't have an equivalent. Phase 3 deferral is honest, not lazy.

## Gotchas (field-tested)

- **Webhook trigger UUIDs collide across envs.** The `webhookId` field in webhook-trigger nodes is what n8n uses to register listeners. If dev and prod share the same UUID on the same instance, one wins. Use `{{HYDRATE:uuid:<name>}}` for `id` AND `webhookId` so hydration assigns a fresh UUID per env.
- **`pinData` hygiene.** Never include `pinData` in templates — it's UI-only test data. Resync strips it; do not re-add it manually.
- **Dev auto-deactivate.** `deploy_all.sh dev` deactivates everything after deploy by default (safety). Use `--keep-active` if you actively need scheduled/webhook triggers running.
- **Position recalculation.** n8n does NOT auto-layout. After inserting/removing nodes, recalculate positions for everything downstream (220px horizontal, 200px vertical). See `pattern-skills/multi-env-uuid-collision.md` for the full positioning rules.
- **Tier ordering for sub-workflows.** Execute Workflow nodes need the callee's ID. Place callees in earlier tiers in `n8n/deployment_order.yaml`.
- **`--debug-deploys` redaction filter.** Trust but verify: `grep -F "$N8N_API_KEY" ~/.cache/n8n-harness/debug/*/deploy-*.json` should return nothing.
- **n8n's public REST has no `run-workflow` endpoint.** That's why every demo uses a Webhook trigger. Manual triggers can only be invoked from the UI; agents can't run them.
- **YAML credential `name` must match n8n's exact credential name.** `id` alone is insufficient — n8n verifies both on activate.

## Interaction notes

- `pattern-skills/` holds reusable n8n authoring patterns (sub-workflows, error handling, credential refs, etc.).
- `integration-skills/<service>/` holds service-specific quirks (Microsoft 365, Gmail, Redis, …) and should be updated when you discover reusable patterns.
- The agent-facing CLI is `n8n-harness`. The bash scripts under `n8n/{deployment,resync}_scripts/` keep their role for non-agent ergonomics.
