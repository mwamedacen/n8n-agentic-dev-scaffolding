---
id: unarchive-workflow
category: lifecycle
difficulty: easy
---

# Unarchive a workflow archived by mistake

## Prompt

> "I archived `daily_report` last week and now I need it back. Unarchive it on prod."

## Expected skills consulted

1. (the harness ships `helpers/unarchive.py` post-task-9; agent finds it the same way as archive.py)

## Expected helpers invoked

1. `helpers/unarchive.py --env prod --workflow-key daily_report`
2. (after unarchive, deploy/activate as needed)

## Expected artifacts

None workspace-side.

## Expected state changes

- Workflow's n8n state changes from archived back to inactive. `PUT /workflows/{id}` works again.

## Success criteria

- [ ] Helper prints `Unarchived workflow '<key>' (id=...) on env 'prod'`.
- [ ] `deploy.py` against the workflow now succeeds (no longer rejected with `Cannot update an archived workflow`).

## Pitfalls

- Unarchive returns the workflow to **inactive** state. To get it actually running again, redeploy (refresh definition) + activate.
- Idempotent on already-active / already-unarchived workflows — the n8n endpoint returns 200 with the workflow object regardless of prior state.
- Like archive, this maps to `POST /api/v1/workflows/{id}/unarchive` — added to public API in 2026-Q1; older n8n versions will 404.
