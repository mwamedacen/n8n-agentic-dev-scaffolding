---
id: deploy-run-assert-oneshot
category: deploy
difficulty: easy
---

# Deploy + run + assert in one shot

## Prompt

> "Deploy `webhook_pinger` to dev, fire it once with payload `{ping: 1}`, and confirm it returns success. Don't make me chain three commands."

## Expected skills consulted

1. `skills/deploy-run-assert.md`

## Expected helpers invoked

1. `helpers/deploy_run_assert.py --env dev --workflow-key webhook_pinger --payload '{"ping":1}' --expect-status success`

## Expected artifacts

- Same as `deploy.py` — hydrated build + deployed workflow.

## Expected state changes

- Workflow deployed + activated + invoked exactly once. Resulting execution recorded on the n8n instance.

## Success criteria

- [ ] Console log shows: hydrate → validate → deploy → run with `--expect-status success` matching → `deploy-run-assert OK`.
- [ ] Exit code 0 only if every stage and the run-status assertion succeed.

## Pitfalls

- `--expect-status` accepts `success` or `error` (post-task-9 fix; pre-fix the flag was hardcoded to `success` internally and not user-overridable).
- For workflows that should deliberately fail (e.g. testing an error handler), pass `--expect-status error`. The helper uses run.py's polling under the hood, so timeout behavior matches `run.py --timeout 30`.
- If deploy succeeds but activate fails (sub-workflow ordering, credential issue), the run stage immediately 404s on the webhook ("not registered"). Fix activation before re-running.
- Don't use this for workflows triggered by anything other than Webhook — `run.py` (and therefore `deploy_run_assert`) only knows how to fire webhooks, with an indirect-dispatch fallback for Error Trigger workflows registered in `common.yml.error_source_to_handler`.

## Notes

The composite is convenient for CI smoke tests and post-deploy verification. For complex multi-step verification, chain the helpers manually.
