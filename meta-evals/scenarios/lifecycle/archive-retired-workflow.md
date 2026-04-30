---
id: archive-retired-workflow
category: lifecycle
difficulty: easy
---

# Archive a retired workflow

## Prompt

> "We're retiring `legacy_quarterly_report`. Archive it on prod so it stops cluttering the UI but we don't lose the history."

## Expected skills consulted

1. (the harness ships `helpers/archive.py` post-task-9; the agent finds it via `--help` or by listing `helpers/`)

## Expected helpers invoked

1. `helpers/deactivate.py --env prod --workflow-key legacy_quarterly_report` (precondition; can't archive an active workflow gracefully)
2. `helpers/archive.py --env prod --workflow-key legacy_quarterly_report`

## Expected artifacts

None workspace-side.

## Expected state changes

- Workflow's n8n state changes to archived. `PUT /workflows/{id}` will reject with `400 {"message":"Cannot update an archived workflow."}` until unarchived.
- Execution history preserved (n8n keeps it).

## Success criteria

- [ ] Helper prints `Archived workflow '<key>' (id=...) on env 'prod'`.
- [ ] Subsequent `dependency_graph.py --source live --env prod` no longer lists the archived workflow under live edges.

## Pitfalls

- Archive is one-way without `unarchive.py`. If you archive by mistake, the harness has the inverse helper — call `unarchive.py` (post-task-9 fix; previously no remediation existed).
- `archive_workflow` calls `POST /api/v1/workflows/{id}/archive` (added to n8n's public API in 2026-Q1). On older n8n versions this 404s — the harness has no fallback for older instances.
- Don't archive a workflow that other workflows still call as a sub-workflow. Their activations will start failing on next deploy with the n8n Cloud sub-workflow caveat.
