---
name: n8n-harness
description: Read-only skill package for authoring, deploying, and operating n8n workflows from code. Routes user requests to lifecycle skills (init, bootstrap-env, create-new-workflow, deploy, run, resync, etc.).
---

# n8n-harness skill router

This is the entry point. When the user asks anything n8n-related, route to the matching sub-skill.

## Mental model

- The skill package (this directory) is **read-only**. You never edit files here.
- The user's project state lives in `${PWD}/n8n-harness-workspace/` (created by `init.md`).
- Helpers are Python scripts under `helpers/`. Invoke them with `python3 <harness>/helpers/<name>.py [args]`.
- All helpers default to `--workspace ${PWD}/n8n-harness-workspace`. Pass `--workspace <path>` if the user runs from elsewhere.

## Lifecycle skills (use when the user wants to do X)

| Skill | When |
|---|---|
| [init.md](skills/init.md) | First-time setup. Creates the workspace at `${PWD}/n8n-harness-workspace/`. |
| [bootstrap-env.md](skills/bootstrap-env.md) | Configure an environment (`dev` / `staging` / `prod`). Creates env YAML + `.env`, validates, mints placeholder workflow IDs. |
| [doctor.md](skills/doctor.md) | Health check. Run before/after major changes. |
| [create-new-workflow.md](skills/create-new-workflow.md) | Author a brand-new workflow. |
| [register-workflow-to-error-handler.md](skills/register-workflow-to-error-handler.md) | Wire `settings.errorWorkflow`. |
| [create-lock.md](skills/create-lock.md) | First-time setup for distributed locking (Redis-backed primitives). |
| [add-lock-to-workflow.md](skills/add-lock-to-workflow.md) | Wrap a workflow's main flow in lock acquire/release. |
| [deploy-single-workflow-in-env.md](skills/deploy-single-workflow-in-env.md) | Deploy one workflow to one env. |
| [activate-single-workflow-in-env.md](skills/activate-single-workflow-in-env.md) | Activate after deploy. |
| [deactivate-single-workflow-in-env.md](skills/deactivate-single-workflow-in-env.md) | Pause triggers (commonly during dev). |
| [deploy-all-workflows-in-env.md](skills/deploy-all-workflows-in-env.md) | Roll out an entire env in tier order. |
| [resync-single-workflow-from-env.md](skills/resync-single-workflow-from-env.md) | Pull live state of one workflow back into its template. |
| [resync-all-workflows-from-env.md](skills/resync-all-workflows-from-env.md) | Snapshot a full env back to templates. |
| [dehydrate-workflow.md](skills/dehydrate-workflow.md) | Convert raw exported JSON into a template. |
| [validate-workflow.md](skills/validate-workflow.md) | Structural REST validation before deploy. |
| [run-workflow.md](skills/run-workflow.md) | Fire a webhook + assert terminal status. |
| [deploy-run-assert.md](skills/deploy-run-assert.md) | One-shot validate → deploy → run verify. |
| [find-skills.md](skills/find-skills.md) | While authoring, find applicable patterns/integrations. |

## Pattern skills (read-only knowledge)

These are reference docs, not action triggers. Read them while authoring.

- `skills/patterns/subworkflows.md`
- `skills/patterns/error-handling.md`
- `skills/patterns/credential-refs.md`
- `skills/patterns/multi-env-uuid-collision.md`
- `skills/patterns/validate-deploy.md`
- `skills/patterns/llm-providers.md`
- `skills/patterns/locking.md`
- `skills/patterns/pindata-hygiene.md`
- `skills/patterns/position-recalculation.md`
- `skills/patterns/prompt-and-schema-conventions.md`

## Integration skills (per-service quirks)

- `skills/integrations/<service>/...md` for `microsoft-365`, `gmail`, `redis`, `slack`, `google-drive`, `notion`, `airtable`, `webhooks`.

## Placeholder syntax (workflow templates)

| Type | Syntax | Source |
|---|---|---|
| `env` | `{{HYDRATE:env:key.path}}` | YAML config value (dot notation) |
| `txt` | `{{HYDRATE:txt:relative/path.txt}}` | Text file in workspace |
| `json` | `{{HYDRATE:json:relative/path.json}}` | JSON file (stringified) |
| `html` | `{{HYDRATE:html:relative/path.html}}` | HTML file |
| `js` | `{{HYDRATE:js:relative/path.js}}` | JavaScript file |
| `uuid` | `{{HYDRATE:uuid:identifier}}` | Fresh UUID v4 (consistent within one hydration) |
