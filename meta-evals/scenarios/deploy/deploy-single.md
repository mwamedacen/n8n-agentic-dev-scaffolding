---
id: deploy-single
category: deploy
difficulty: trivial
---

# Deploy a single workflow

## Prompt

> "Deploy `daily_report` to dev."

## Expected skills consulted

1. `skills/deploy.md`

## Expected helpers invoked

1. `helpers/deploy.py --env dev --workflow-key daily_report`

## Expected artifacts

- `n8n-build/dev/daily_report.generated.json` (hydrated; created if missing).

## Expected state changes

- Workflow PUT to `<base>/api/v1/workflows/<id>` and activated via `POST /workflows/<id>/activate`.

## Success criteria

- [ ] Helper prints `Deployed workflow '<key>' (id=...) on env 'dev'` then `Activated workflow '<key>'`.
- [ ] Exit code 0.

## Pitfalls

- If hydrate fails (e.g. sentinel placeholder, missing JS file), deploy bails with a clear ValueError. Fix the underlying issue — don't pass `--no-activate` to "skip the problem".
- If only activation fails (PUT succeeded), helper exits **2** — distinct from PUT failure exit 1. `deploy_all.py` treats 2 as warn-and-continue by default. The PUT-only-success state is recoverable: activate manually after fixing whatever blocked the original activate (commonly: a sub-workflow that wasn't itself activated yet).
- Use `--rehydrate` to force re-hydration if the build is stale and you've edited the template since.

## Notes

`deploy.py` calls `hydrate.py` automatically if the build is missing. You don't need to hydrate first explicitly.
