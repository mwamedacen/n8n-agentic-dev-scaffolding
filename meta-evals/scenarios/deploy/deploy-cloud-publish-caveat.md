---
id: deploy-cloud-publish-caveat
category: deploy
difficulty: hard
---

# Deploy a caller workflow on n8n Cloud (publish ordering caveat)

## Prompt

> "Deploy my `order_processor` workflow that calls `pricing_calc` as a sub-workflow. We're on n8n Cloud."

## Expected skills consulted

1. `skills/deploy.md` (the "n8n Cloud sub-workflow caveat" section)
2. `skills/deploy_all.md`

## Expected helpers invoked

Preferred path:
1. `helpers/deploy_all.py --env prod` — handles tier ordering automatically (callees first).

Fallback (manual):
1. `helpers/deploy.py --env prod --workflow-key pricing_calc` (must succeed activation)
2. `helpers/deploy.py --env prod --workflow-key order_processor`

## Expected artifacts

- Both built JSONs under `n8n-build/prod/`.

## Expected state changes

- Both workflows deployed and activated, in the right order.

## Success criteria

- [ ] Caller's `/activate` returns 200, NOT 400.
- [ ] Caller webhook produces a successful execution that fans out to callee.

## Pitfalls

- **n8n Cloud rejects activation of a workflow whose Execute Workflow targets aren't themselves active**, with `400 {"message":"Cannot publish workflow: Node X references workflow Y which is not published. Please publish all referenced sub-workflows first."}`.
- n8n's **public REST API has NO `/publish` endpoint**. `POST /workflows/{id}/activate` IS the publish action — n8n renamed the UI verb but the API path stayed. The harness's `activate.py` already calls the right endpoint; the issue is purely activation ordering.
- Self-hosted instances generally don't enforce this; the caveat is Cloud-specific. If you switch from self-hosted to Cloud and a previously-working workflow suddenly 400s on activate, this is why.
- If you hit the 400, deactivate the parent (if previously active), activate the callee, re-deploy the parent. Or use `deploy_all.py` from a fresh state.

## Notes

This was a real adversarial finding from the audit (task-9 finding #1). The fix is documentation-as-ceiling — there's no harness change that would bypass n8n's enforcement.
