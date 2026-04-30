---
id: deactivate-prod-single
category: lifecycle
difficulty: trivial
---

# Deactivate a single workflow in prod

## Prompt

> "Pause `payment_processing` on prod immediately — there's a bug we're investigating. Don't archive, just stop it from running."

## Expected skills consulted

1. `skills/deactivate-single-workflow-in-env.md`

## Expected helpers invoked

1. `helpers/deactivate.py --env prod --workflow-key payment_processing`

## Expected artifacts

None workspace-side.

## Expected state changes

- Workflow's n8n state: active → inactive. Its triggers (webhook / schedule / cron) stop firing. In-flight executions complete normally.

## Success criteria

- [ ] Helper prints `Deactivated workflow '<key>' (id=...) on env 'prod'`.
- [ ] Subsequent `list_executions.py` shows no new executions starting after the deactivate timestamp.

## Pitfalls

- Deactivating a workflow that's referenced as a sub-workflow by an active caller will **break the caller's next activation attempt** (the caller can't activate when the callee is inactive). Either deactivate the caller first or accept that the chain is now offline.
- Webhook URLs return 404 for inactive workflows. Test with `curl` after deactivate to confirm the trigger is actually inactive.
- For a TEMPORARY pause (you'll reactivate within minutes), prefer `deactivate.py` over `archive.py`. Archive is for retiring.
