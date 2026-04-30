---
id: resync-single
category: resync
difficulty: easy
---

# Resync one workflow from the live env

## Prompt

> "Pull `report_v2`'s current state from staging back into my workspace template."

## Expected skills consulted

1. `skills/resync.md`

## Expected helpers invoked

1. `helpers/resync.py --env staging --workflow-key report_v2`

## Expected artifacts

- `n8n-workflows-template/report_v2.template.json` updated.

## Expected state changes

None on the n8n instance — read-only.

## Success criteria

- [ ] Helper prints `Resynced workflow 'report_v2' from env 'staging' → ...`.
- [ ] `git diff` shows only meaningful changes (placeholders preserved, metadata stripped).

## Pitfalls

- Resync overwrites your local template — commit local edits FIRST.
- Diff size depends on how much UI-side editing happened. A clean round-trip on an unchanged workflow shows ~30 meaningful lines (mostly whitespace formatting differences between hand-authored compact JSON and n8n's pretty-print).
