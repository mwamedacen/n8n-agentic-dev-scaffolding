---
id: add-redis-lock-per-resource
category: resilience
difficulty: medium
---

# Add a Redis lock to a workflow with per-resource scope

## Prompt

> "My workflow `sharepoint_writeback` shouldn't run concurrently for the same Excel file — concurrent calls clobber each other's writes. Add a Redis lock scoped per `fileId`, with a 10-minute TTL and 60-second wait."

## Expected skills consulted

1. `skills/create-lock.md`
2. `skills/add-lock-to-workflow.md`
3. `skills/integrations/redis/lock-pattern.md`

## Expected helpers invoked

1. `helpers/create_lock.py` (if lock primitives aren't yet in the workspace)
2. `helpers/add_lock_to_workflow.py --workflow-key sharepoint_writeback --scope-expression "={{ 'excel-' + \$json.fileId }}" --ttl-seconds 600 --max-wait-seconds 60`
3. `helpers/validate.py --workflow-key sharepoint_writeback`
4. `helpers/deploy.py --env dev --workflow-key sharepoint_writeback`

## Expected artifacts

- `lock_acquisition.template.json`, `lock_release.template.json` (and registered in env YAMLs).
- `sharepoint_writeback.template.json` updated to splice in `Lock Acquire` after the trigger and `Lock Release` after the main flow.
- `<env>.yml.lockScopes` may NOT gain a literal entry — the scope is dynamic (`$json.fileId`). Helper prints a NOTE asking the operator to add real scope strings manually if active error-handler cleanup is needed.

## Expected state changes

- Workflow deployed + activated. First call per `fileId` acquires; concurrent calls for same file wait up to 60s; concurrent calls for different files run in parallel.

## Success criteria

- [ ] Two concurrent `curl`s with same `fileId` → first succeeds in ~3s, second waits then either succeeds or times out at 60s (whichever first releases).
- [ ] Two concurrent `curl`s with different `fileId`s → both succeed in ~3s parallel.
- [ ] Redis keys observed: `n8n-lock-excel-<fileId>` (counter) + `n8n-lock-excel-<fileId>:meta` (JSON identity sidecar).

## Pitfalls

- **Always use canonical `={{ ... }}` form** for `--scope-expression`. Bare `=<expr>` (without `{{ }}`) is auto-wrapped (with deprecation warning) by the helper since post-task-12 fixes; pre-fix, it silently degraded to a literal-string single-global lock.
- Lock primitives must already be deployed and active (`Tier 0a: leaves` in deployment_order.yml). If `lock_acquisition` itself isn't active, parent activation 400s with the n8n Cloud sub-workflow caveat.
- The TTL bounds crashed-holder leak time, NOT wait time. Wait time is `--max-wait-seconds`. Don't conflate.
- Dynamic scopes are NOT auto-registered in `lockScopes` — error-handler active cleanup will silently skip them. Either accept TTL-only cleanup or maintain `lockScopes` manually.

## Notes

Per-resource scoping is the most common lock use case. For one-execution-at-a-time (no per-resource semantics), use `--scope-expression "={{ $execution.id }}"` (the default). For one-globally, use `={{ "global" }}` or `global` (literal).
