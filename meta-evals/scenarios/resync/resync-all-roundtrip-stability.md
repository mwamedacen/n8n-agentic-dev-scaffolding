---
id: resync-all-roundtrip-stability
category: resync
difficulty: medium
---

# Resync_all to verify round-trip stability across an env

## Prompt

> "Snapshot the entire dev env back into my workspace. I want to commit the current state as a clean baseline."

## Expected skills consulted

1. `skills/resync_all.md`

## Expected helpers invoked

1. `helpers/resync_all.py --env dev`

## Expected artifacts

- Every workflow listed in `dev.yml.workflows` gets resynced into its `*.template.json`.

## Expected state changes

None — read-only across the env.

## Success criteria

- [ ] All workflows in dev.yml round-tripped without errors.
- [ ] `git diff --stat n8n-workflows-template/` is bounded — drift per workflow ~30 meaningful lines max post-task-9 metadata strip.

## Pitfalls

- **Round-trip is template-stable, NOT byte-stable**. README's pre-task-9 claim of byte-stability was inaccurate; corrected to template-stable. Whitespace + a few leaf-level UUIDs (`webhookId`, `parameters.assignments[].id`, `parameters.conditions[].id`) drift on every round-trip. Treat as benign.
- Long workspaces with 30+ workflows produce a noisy `git diff` even on clean round-trips. To distinguish "real changes" from "round-trip noise", inspect specific keys (e.g. workflows you've actually modified in the UI).
- If a workflow's hydrate would currently fail (e.g. sentinel placeholder, missing JS file), resync still works — it doesn't go through hydrate. But the resulting template will fail subsequent deploy.

## Notes

The README claim used to say "byte-stable"; it now says "template-stable: placeholder structure, JS/Python code blocks, env refs, and UUIDs all survive a hydrate→deploy→resync cycle. Whitespace formatting and a few leaf-level UUIDs are not currently round-trip-restored."
