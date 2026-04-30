---
id: promote-dev-to-staging
category: multi-env
difficulty: medium
---

# Promote a workflow from dev to staging

## Prompt

> "I've been iterating on `daily_report` in dev. Promote it to staging — I want it deployed and active there."

## Expected skills consulted

1. `skills/deploy.md`
2. `skills/bootstrap-env.md` (if `daily_report` isn't yet registered in staging's YAML)

## Expected helpers invoked

1. `helpers/bootstrap_env.py --env staging` (if needed, mints a placeholder workflow id for `daily_report` in `staging.yml`).
2. `helpers/validate.py --env staging --workflow-key daily_report --source built` (after hydrate)
3. `helpers/deploy.py --env staging --workflow-key daily_report`

## Expected artifacts

- `n8n-config/staging.yml.workflows.daily_report.id` is now a real n8n id (was empty / sentinel before).
- `n8n-build/staging/daily_report.generated.json` (hydrated against staging YAML, so credentials / workflow ids are staging-specific).

## Expected state changes

- Workflow deployed and activated on staging.

## Success criteria

- [ ] `doctor.py --env staging` returns `verdict: "ok"`.
- [ ] `list_executions.py --env staging --workflow-key daily_report` shows it's reachable.
- [ ] dev's `daily_report` is unchanged — promotion is one-way.

## Pitfalls

- `n8n-workflows-template/daily_report.template.json` is shared across envs. Per-env divergence comes ONLY from `<env>.yml` (workflow ids, credential ids, displayName, postfix).
- If `daily_report` references a credential like `{{@:env:credentials.shop_api.id}}`, that credential must also exist on staging. Run `manage_credentials.py list-link --env staging --type ... --from-name ...` first if not.
- Don't manually copy a deployed workflow's JSON from dev to staging — that bakes in dev's credential ids. Always hydrate per-env.
