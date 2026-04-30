---
id: register-error-handler
category: resilience
difficulty: easy
---

# Register an error-handler workflow for failures

## Prompt

> "When `payment_processing` fails, route the error to my existing error workflow `notify_oncall` so we get a Slack ping. Also wire `notify_oncall` itself if it's not yet in the workspace."

## Expected skills consulted

1. `skills/register-workflow-to-error-handler.md`
2. `skills/patterns/error-handling.md`

## Expected helpers invoked

1. `helpers/register_error_handler.py --workflow-key payment_processing --handler-key notify_oncall`

## Expected artifacts

- `n8n-workflows-template/payment_processing.template.json` gains `settings.errorWorkflow: "{{@:env:workflows.notify_oncall.id}}"`.
- `n8n-config/common.yml` updated with `error_source_to_handler.payment_processing: notify_oncall` (so `run.py` can do indirect dispatch via the source workflow when running the handler for testing).

## Expected state changes

After the next deploy of `payment_processing`, n8n-side `settings.errorWorkflow` points at `notify_oncall`. n8n auto-fires the handler on any unhandled error in the source.

## Success criteria

- [ ] `payment_processing` errors → handler execution recorded with `mode: "error"` in `list_executions.py --workflow-key notify_oncall`.
- [ ] `dependency_graph.py --env dev` shows the error-handler edge under "error_handlers".

## Pitfalls

- The handler workflow must use `n8n-nodes-base.errorTrigger` (not Webhook). It receives the failed execution's metadata at `$('Error Trigger').first().json`.
- `run.py` for the handler indirectly fires the source workflow — `error_source_to_handler` is the lookup map. If it's not set, `run.py` errors with "no webhook node to fire directly" because Error Trigger workflows have no webhook entry.
- Don't forget to deploy the SOURCE workflow after wiring — n8n picks up `settings.errorWorkflow` from the deployed PUT, not from the workspace template.
