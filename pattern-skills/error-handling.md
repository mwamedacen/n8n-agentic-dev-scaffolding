# Error handling: Error Trigger workflows

## When to use

When a workflow needs to clean up after a failure — release locks, post a Slack alert, write to an audit log — wire its `errorWorkflow` setting to a separate workflow whose entry point is an Error Trigger (`n8n-nodes-base.errorTrigger`).

## Mechanics

1. Author the error handler as a normal workflow with an Error Trigger entry node:

   ```json
   {
     "type": "n8n-nodes-base.errorTrigger",
     "name": "On Workflow Error",
     "parameters": {}
   }
   ```

2. In the workflow that should fire it, set the error workflow ID in `settings`. **No `=` prefix** — n8n's `settings.errorWorkflow` expects a literal workflow id, not an expression:

   ```json
   "settings": {
     "executionOrder": "v1",
     "errorWorkflow": "{{HYDRATE:env:workflows.error_handler_lock_cleanup.id}}"
   }
   ```

   (If you write `"={{HYDRATE:env:...}}"` with the leading `=`, n8n treats the whole thing as an expression and the literal id never gets substituted at activation time — silent failure.)

3. In `n8n/deployment_order.yaml`, place the error handler BEFORE any workflow that references it (the referencer needs the handler's id at deploy time).

## Testing the routing programmatically: the source/handler pair pattern

Error Trigger workflows can't be fired directly via REST — they fire only when another workflow whose `settings.errorWorkflow` points at them fails. To test an Error Trigger workflow programmatically, build a paired "source" workflow:

```
demo_X_handler              ← Error Trigger workflow (the one you want to test)
demo_X_source               ← Webhook-triggered helper that intentionally throws,
                              with settings.errorWorkflow → demo_X_handler.id
```

When you fire `demo_X_source`'s webhook:
- `demo_X_source` runs, throws → exits with `status="error"`
- n8n routes the error context to `demo_X_handler`
- `demo_X_handler` runs, captures the context → exits with `status="success"`

The harness ships the canonical example: `demo_error_source` + `demo_error_handler`. `helpers.run_workflow("demo_error_handler")` is special-cased via `_INDIRECT_VIA_ERROR_SOURCE` to do all this transparently — fire the source, poll the handler. See `n8n/workflows/AGENTS.md` for the full table.

## Worked example: existing `error_handler_lock_cleanup`

`n8n/environments/dev.yaml` ships with `error_handler_lock_cleanup`: when a pipeline that holds a Redis lock crashes, the error handler is invoked with the original execution payload, looks up the lock key, and releases it. The pipeline references it via:

```json
"settings": {
  "errorWorkflow": "={{HYDRATE:env:workflows.error_handler_lock_cleanup.id}}"
}
```

The Error Trigger receives the failing execution's data including `error.message`, `error.stack`, and the input payload of the node that failed. Use that to decide cleanup.

## Common traps

- **Error workflow not activated.** Even if the parent is active, the error workflow must also be active for n8n to trigger it.
- **Error trigger fires only on activated workflows.** Manual test runs in the UI do NOT fire the error workflow on failure — they show the error inline. Real failures from active triggers do.
- **Tight loops between handler and parent.** If the error handler itself can fail, do not set its own `errorWorkflow` to itself. n8n won't infinite-loop, but will silently drop the second-order failure.
