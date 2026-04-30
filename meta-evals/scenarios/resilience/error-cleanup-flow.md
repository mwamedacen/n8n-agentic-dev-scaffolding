---
id: error-cleanup-flow
category: resilience
difficulty: hard
---

# Wire active error-handler cleanup for orphaned locks

## Prompt

> "When a locked workflow crashes, its lock should get released automatically — not wait for the TTL. Set up the active-cleanup error handler."

## Expected skills consulted

1. `skills/create-lock.md` (with `--include-error-handler`)
2. `skills/add-lock-to-workflow.md` (with `--lock-on-error`)
3. `skills/integrations/redis/lock-pattern.md`

## Expected helpers invoked

1. `helpers/create_lock.py --include-error-handler` (copies `error_handler_lock_cleanup.template.json` into the workspace + registers).
2. `helpers/add_lock_to_workflow.py --workflow-key risky_workflow --scope-expression "={{ 'global' }}" --lock-on-error` (the helper auto-registers `global` in `<env>.yml.lockScopes`).
3. `helpers/deploy.py --env dev --workflow-key error_handler_lock_cleanup` and the source workflow.

## Expected artifacts

- `n8n-config/dev.yml.lockScopes` includes `global` (auto-appended).
- `risky_workflow.template.json` has `settings.errorWorkflow` pointing at `{{@:env:workflows.error_handler_lock_cleanup.id}}`.

## Expected state changes

- When `risky_workflow` errors, the error handler fires, iterates `lockScopes`, GETs each `n8n-lock-<scope>:meta`, parses, and DELs only the entries whose `execution_id` matches the failed execution.

## Success criteria

- [ ] Trigger a deliberate failure inside the locked critical section.
- [ ] List handler executions: `list_executions.py --workflow-key error_handler_lock_cleanup --limit 5` shows a `mode: "error"` execution with `cleaned: true, cleaned_count: 1`.
- [ ] Redis keys `n8n-lock-global` and `n8n-lock-global:meta` are gone (DEL'd by handler) before the TTL fires.

## Pitfalls

- **Empty / missing `lockScopes`** → handler emits `cleaned: false, reason: "no lockScopes registered…"` and exits cleanly. Check the log entry; doctor `--json` with verdict `lock-scopes-unregistered` flags this preemptively.
- **Dynamic scope expressions don't auto-register**. If your lock uses `={{ "lock-" + $json.x }}`, the static-extractor returns null and the helper prints a NOTE asking you to maintain `lockScopes` manually. Without that, error-handler will silently skip your lock on crash and you'll wait for the TTL.
- **Ownership check matters**: handler only DELs entries whose `parsedMeta.execution_id === failed_execution_id`. If two executions hold different scopes and one crashes, the handler cleans up only the crashed one.
- The `:meta` sidecar's TTL matches the counter's; if both expire before the handler runs, there's nothing to clean. That's fine — TTL self-heal is the backstop.

## Notes

Active cleanup eliminates the TTL-window block from the prior no-op-stub design. Worth wiring for hot scopes where waiting `ttl_seconds` (default 24h) for self-heal is unacceptable.
