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

2. In the workflow that should fire it, set the error workflow ID in `settings`:

   ```json
   "settings": {
     "executionOrder": "v1",
     "errorWorkflow": "={{HYDRATE:env:workflows.error_handler_lock_cleanup.id}}"
   }
   ```

3. In `n8n/deployment_order.yaml`, place the error handler in tier 1 (it's a callee).

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
