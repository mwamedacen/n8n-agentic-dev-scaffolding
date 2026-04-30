---
id: rollback-deactivate-redeploy
category: multi-env
difficulty: medium
---

# Roll back a bad prod deploy

## Prompt

> "I just deployed `payment_processing` to prod and it's failing. Roll back to the previous version."

## Expected skills consulted

1. `skills/deactivate-single-workflow-in-env.md`
2. `skills/deploy.md`

## Expected helpers invoked

1. `helpers/deactivate.py --env prod --workflow-key payment_processing` (stop the bleeding)
2. (agent uses `git log -- n8n-workflows-template/payment_processing.template.json` to find the previous good revision)
3. `git checkout <good-sha> -- n8n-workflows-template/payment_processing.template.json`
4. `helpers/validate.py --workflow-key payment_processing --env prod`
5. `helpers/deploy.py --env prod --workflow-key payment_processing`

## Expected artifacts

- Workspace template reverted to the prior good revision (in working tree, NOT committed yet).

## Expected state changes

- Prod-side workflow deactivated → redeployed → reactivated. Briefly inactive during the rollback window.

## Success criteria

- [ ] `list_executions.py --env prod --workflow-key payment_processing --started-after <rollback-time>` shows new executions are succeeding.
- [ ] `git diff` reflects the revert — agent should remind the user to commit the rollback (or revert the revert if a forward-fix is preferred).

## Pitfalls

- **n8n has no native "deploy a previous version" via the public API** — n8n's versioning is internal. The harness rollback path is via the workspace's git history. If the previous deploy didn't go through git, you can't roll back via this method.
- If the bad workflow had executions in flight at the time of deactivate, those will fail (or run to completion depending on n8n's timing). Inspect `list_executions.py` for executions in `running` status during the rollback window.
- If the prior good version referenced credentials that are no longer linked, redeploy will succeed at PUT time but fail at execution. Verify credential placeholders resolve cleanly via `hydrate.py` first.
- For Cloud, "deactivate then redeploy then activate" is the canonical rollback. Don't try to clone a workflow under a new id — it diverges from the workspace's source-of-truth.
