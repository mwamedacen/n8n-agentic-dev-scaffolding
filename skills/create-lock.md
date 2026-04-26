---
name: create-lock
description: First-time setup for distributed locking — copy lock primitive templates into the workspace.
---

# create-lock

## When

First time the user wants distributed-locking semantics in their workflows.

## How

```bash
python3 <harness>/helpers/create_lock.py [--include-error-handler]
```

## Side effects

- Copies these primitives from `<harness>/primitives/workflows/` into `<workspace>/n8n-workflows-template/`:
  - `lock_acquisition.template.json`
  - `lock_release.template.json`
  - (with `--include-error-handler`) `error_handler_lock_cleanup.template.json`
- Registers each in every configured env's YAML (delegates to `create_workflow.py --no-template`).
- Adds them to `deployment_order.yml` under "Tier 0a: leaves".

After this skill, the user owns the lock primitives in their workspace; the harness's seed copies stay untouched.

## Pattern

See `skills/patterns/locking.md` for the lock contract (scope expressions, when to use, etc.).

## Next step

Use `add-lock-to-workflow.md` to wrap a critical workflow's flow in lock acquire / release.
