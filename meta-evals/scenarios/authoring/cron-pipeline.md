---
id: cron-pipeline
category: authoring
difficulty: easy
---

# Cron-triggered multi-step pipeline

## Prompt

> "Every weekday at 9am, fetch yesterday's orders from our shop API, transform them with a JS function, and write the result to a Postgres table called `daily_orders`. Workflow key: `daily_orders_etl`."

## Expected skills consulted

1. `skills/create-new-workflow.md`
2. `skills/patterns/code-node-discipline.md`
3. `skills/manage-credentials.md` (the agent must verify Postgres + shop-API credentials are linked)

## Expected helpers invoked

1. `helpers/create_workflow.py --key daily_orders_etl --name "Daily Orders ETL" --register-in dev --tier "Tier 2"`
2. (template authoring: Schedule Trigger → HTTP Request → Code → Postgres)
3. `helpers/test_functions.py --target n8n`
4. `helpers/validate.py --workflow-key daily_orders_etl`
5. `helpers/deploy.py --env dev --workflow-key daily_orders_etl`

## Expected artifacts

- `n8n-workflows-template/daily_orders_etl.template.json` with `n8n-nodes-base.scheduleTrigger` (or `cron`) at the head.
- `n8n-functions/js/transformOrders.js` + paired test.

## Expected state changes

- Workflow deployed + activated on dev. Schedule Trigger fires server-side; no manual webhook needed for verification.

## Success criteria

- [ ] First scheduled run produces a `success` execution visible via `list_executions.py --workflow-key daily_orders_etl`.
- [ ] `daily_orders` table has the expected rows.
- [ ] `validate.py` clean.

## Pitfalls

- Cron expression syntax: n8n uses `Mon-Fri 09:00` shorthand under the Schedule Trigger node, NOT the classical 5-field `0 9 * * 1-5` format. Cron-classic format is supported via the older `n8n-nodes-base.cron` node but Schedule Trigger is the modern path.
- HTTP Request to the shop API needs its credential linked first (`manage_credentials.py list-link --type httpHeaderAuth ...`). If the credential placeholder `{{@:env:credentials.shop_api.id}}` resolves to the bootstrap sentinel, hydrate refuses with a clear pointer to bootstrap-env.
- Postgres credential type is `postgres`, not `pg` or `postgresql` — match n8n's exact type name when calling `list-link`.
