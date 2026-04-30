---
id: resync-staging
category: multi-env
difficulty: easy
---

# Resync a staging workflow back into the workspace

## Prompt

> "Someone tweaked `report_v2` in staging via the n8n UI. Pull those changes back into my workspace template so I don't overwrite them on next deploy."

## Expected skills consulted

1. `skills/resync.md`

## Expected helpers invoked

1. `helpers/resync.py --env staging --workflow-key report_v2`

## Expected artifacts

- `n8n-workflows-template/report_v2.template.json` updated with the staging-side changes, with:
  - Volatile metadata stripped (id, active, versionId, createdAt, updatedAt, tags, pinData, description, staticData, activeVersionId, versionCounter, activeVersion).
  - Env values reverse-substituted back to `{{@:env:displayName}}`, `{{@:env:workflowNamePostfix}}`, etc.
  - JS / Python code blocks collapsed back to `{{@:js:...}}` / `{{@:py:...}}` placeholders via round-trip markers.
  - UUID placeholders restored on top-level node `id` fields by node-name lookup against the prior template.

## Expected state changes

None on the n8n instance — resync is GET-only.

## Success criteria

- [ ] `git diff n8n-workflows-template/report_v2.template.json` shows only the meaningful changes from staging (typically <30 meaningful lines after task-9 metadata strip extension).
- [ ] No leaked `description: null`, `staticData: null`, etc. in the diff.
- [ ] The existing `{{@:env:...}}` and `{{@:js:...}}` placeholders are preserved — not replaced with their substituted values.

## Pitfalls

- Resync overwrites your workspace template — commit any local edits BEFORE resyncing if they aren't yet on staging.
- `webhookId`, `parameters.assignments[].id`, `parameters.conditions[].id` UUIDs are NOT round-trip-restored (deeper-walker not implemented). They'll appear as real UUIDs in the resynced template. This is documented; treat as benign.
- If you resync into a key that has no prior template, UUID placeholders won't be restored at all — there's no source-of-truth mapping to apply.
