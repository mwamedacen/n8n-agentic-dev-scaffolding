---
id: resync-after-ui-edit-drift
category: resync
difficulty: medium
---

# Detect drift after UI edits

## Prompt

> "I think someone edited `daily_orders_etl` in the n8n UI directly. Confirm what changed and whether I should pull it back or overwrite."

## Expected skills consulted

1. `skills/resync.md`
2. `skills/diff.md` (if exists; otherwise the agent uses `git diff` after resync to a temp file)

## Expected helpers invoked

1. (agent saves the current template to /tmp first as a baseline)
2. `helpers/resync.py --env dev --workflow-key daily_orders_etl`
3. `git diff` (or equivalent) on the template file.

## Expected artifacts

- /tmp baseline of the pre-resync template.
- Updated `n8n-workflows-template/daily_orders_etl.template.json` reflecting live state.
- `git diff` output the agent reads to assess drift.

## Expected state changes

None on the n8n instance.

## Success criteria

- [ ] Diff isolates real changes from round-trip noise.
- [ ] Agent surfaces a recommendation: "pull it" (commit the resynced template), "overwrite it" (revert + redeploy from workspace), or "merge" (cherry-pick specific changes).

## Pitfalls

- The harness can't tell you WHO edited the workflow or WHEN — that's not in `GET /workflows/{id}`'s response. Operator must check n8n's UI activity log.
- If the UI editor added a node that the workspace doesn't know about (e.g. a new credential reference), the resynced template will reference a real n8n credential id — which is workspace-non-portable. Either link the credential to the workspace YAML (`manage_credentials.py list-link`) or replace the literal id with a `{{@:env:credentials.<key>.id}}` placeholder by hand.
- Round-trip noise (whitespace, leaf UUIDs) inflates the diff. Use `git diff -w` to ignore whitespace-only changes for a quick read.

## Notes

This is the canonical "live drift" workflow. If your team commits resynced templates regularly, drift stays small. If resyncs are rare, drift accumulates and the diff becomes a haystack.
