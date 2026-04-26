---
name: pattern-error-handling
description: Error Trigger workflows + the source/handler-pair indirect-dispatch pattern.
---

# Pattern: error handling

n8n supports per-workflow error handlers via `settings.errorWorkflow`. When the source workflow errors, n8n routes the error data to the handler workflow (which uses `n8n-nodes-base.errorTrigger` as its entry).

## Wiring

Use `register-workflow-to-error-handler.md`:

```bash
python3 <harness>/helpers/register_error_handler.py --workflow-key <wf> --handler-key <handler>
```

This sets `settings.errorWorkflow = "{{HYDRATE:env:workflows.<handler>.id}}"` (literal placeholder, no `=` prefix — n8n expects a literal id).

It also writes to `<workspace>/n8n-config/common.yml.error_source_to_handler[<wf>] = <handler>` so `run.py` knows about the pairing for indirect dispatch.

## Indirect dispatch

Error Trigger workflows have no Webhook entry — you can't fire them directly. To run / verify a handler, fire the **paired source** workflow (which is supposed to error and route to the handler). `run.py` does this automatically when the requested key is a known handler:

```bash
python3 <harness>/helpers/run.py --env dev --workflow-key error_handler_lock_cleanup
# → reverse-looks-up the source key from common.yml.error_source_to_handler
# → fires that source's webhook (expecting it to error)
# → polls the handler's executions for the routed error
```

## Lock cleanup pattern

The canonical use-case: a workflow that holds a Redis lock might crash before reaching `lock_release`. Wire `error_handler_lock_cleanup` as the source's error workflow so locks always get released. See `skills/patterns/locking.md`.
