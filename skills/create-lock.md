---
name: create-lock
description: First-time setup for distributed locking + rate-limit — copy the coordination primitives into the workspace.
---

# create-lock

## When

First time the user wants distributed-locking or rate-limiting semantics in their workflows.

## How

```bash
python3 <harness>/helpers/create_lock.py \
  [--include-error-handler] \
  [--include-rate-limit] \
  [--force-overwrite]
```

## Side effects

- Copies these primitives from `<harness>/primitives/workflows/` into `<workspace>/n8n-workflows-template/`:
  - `lock_acquisition.template.json` (always)
  - `lock_release.template.json` (always)
  - `error_handler_lock_cleanup.template.json` (with `--include-error-handler`)
  - `rate_limit_check.template.json` (with `--include-rate-limit`)
- Registers each in every configured env's YAML (delegates to `create_workflow.py --no-template`).
- Adds them to `deployment_order.yml` under "Tier 0a: leaves".

After this skill, the user owns the primitives in their workspace; the harness's seed copies stay untouched.

## Flag details

- **`--include-error-handler`** — also copy `error_handler_lock_cleanup`. Use when you'll add `--lock-on-error` to any workflow via `add-lock-to-workflow`.
- **`--include-rate-limit`** — also copy `rate_limit_check`. Required before `add-rate-limit-to-workflow` will run.
- **`--force-overwrite`** — overwrite existing workspace copies of the primitives instead of skipping them. Default off (preserves idempotence). Without the flag, an already-present primitive triggers a warning:
  ```
  WARNING: <key>.template.json already exists — re-run with --force-overwrite
  to update to the real Redis implementation.
  ```
  Use this flag when upgrading from an earlier harness version that shipped placeholder Set-node primitives — it pulls the current real-Redis bodies in.

## Pattern

See `skills/patterns/locking.md` for the lock + rate-limit contracts (scope expressions, when to use each mode).

## Next steps

- `add-lock-to-workflow.md` to wrap a workflow's flow in lock acquire / release (with optional wait-on-lock).
- `add-rate-limit-to-workflow.md` to gate a workflow with a rate-limit check (requires `--include-rate-limit`).
