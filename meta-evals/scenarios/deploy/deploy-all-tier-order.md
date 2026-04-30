---
id: deploy-all-tier-order
category: deploy
difficulty: easy
---

# Deploy every workflow in tier order

## Prompt

> "Roll out the whole dev env. Make sure leaves go before parents."

## Expected skills consulted

1. `skills/deploy_all.md`

## Expected helpers invoked

1. `helpers/deploy_all.py --env dev`

## Expected artifacts

- `n8n-build/dev/<key>.generated.json` for each tier-listed workflow.

## Expected state changes

- Each workflow PUT + activated in order. After all deploys, dev-only workflows with external triggers (webhook / schedule / cron) get auto-deactivated unless `--keep-active` is passed (avoids burning quota on dev-only triggers).

## Success criteria

- [ ] Console log shows `=== Tier: <name> ===` markers in the configured order (alphabetical by tier key — e.g. `Tier 0a: leaves` before `Tier 1`).
- [ ] All deploys succeed; final line is `deploy_all complete.` (or `… complete with N failure(s)` if any failed).

## Pitfalls

- Tier ordering is alphabetical on tier-key. `Tier 0a: leaves` < `Tier 0b: handlers` < `Tier 1` lexicographically. If you name tiers `Leaves` and `Parents`, ordering is `L < P` and you may not get what you want — use the numbered convention.
- Workflows not in `deployment_order.yml` are skipped entirely. To check coverage, compare `<env>.yml.workflows.*` keys against the tiered list.
- Activate failures (deploy.py exit 2) are warn-and-continue by default. Use `--strict-activate` to fail-fast when activation matters (prod rollouts).
- The dev-only auto-deactivate at the end uses `_has_external_trigger` to detect web-facing workflows. Sub-workflows and error handlers stay active so parent workflows don't break.
