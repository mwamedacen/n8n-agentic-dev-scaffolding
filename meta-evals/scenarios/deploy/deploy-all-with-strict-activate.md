---
id: deploy-all-with-strict-activate
category: deploy
difficulty: medium
---

# Deploy_all with strict-activate (prod-style fail-fast)

## Prompt

> "Roll out to prod, but stop the rollout immediately if any workflow fails to activate. I'd rather catch a misconfig than deploy half a stack."

## Expected skills consulted

1. `skills/deploy_all.md`

## Expected helpers invoked

1. `helpers/deploy_all.py --env prod --strict-activate`

## Expected artifacts

- Same as deploy-all-tier-order — built generated.json files per workflow.

## Expected state changes

- If every workflow's PUT and ACTIVATE both succeed: full env deployed.
- If any activation fails (e.g. sub-workflow not yet active, credential ref invalid, n8n-cloud sub-workflow ordering issue): rollout halts at that tier, prior tiers stay deployed. Operator investigates before retrying.

## Success criteria

- [ ] On clean run: same as deploy-all-tier-order (`deploy_all complete.`).
- [ ] On activate failure: helper prints `FAIL: deploy '<key>' exit=2` and exits non-zero. No further tiers attempted.

## Pitfalls

- **Default is warn-and-continue** for activate failures. `--strict-activate` flips that to fail-fast. PUT failures (exit 1) always halt regardless of the flag.
- For prod: prefer `--strict-activate` so a partial deploy doesn't go unnoticed.
- For dev iteration: the default is friendlier — finish what you can, fix the rest manually.
- The exit-2 vs exit-1 distinction lives in `deploy.py`, which `deploy_all` invokes per-key. `deploy.py` exits 2 specifically when PUT succeeded but `/activate` 400'd or 5xx'd.

## Notes

The warn-and-continue default came from task-9 finding #7. Pre-fix, all activate failures hard-stopped the tier even when downstream workflows didn't depend on the failed one. The `--strict-activate` opt-in lets operators choose the behavior per-environment.
