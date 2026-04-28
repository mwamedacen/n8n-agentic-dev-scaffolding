---
name: create-lock
description: First-time setup for distributed locking + rate-limit — copy the coordination primitives into the workspace AND register them in env YAMLs.
user-invocable: false
---

# create-lock

## When

First time the user wants distributed-locking or rate-limiting semantics in their workflows.

This skill is the **bundled** entry point: it copies the lock pair (lock_acquisition + lock_release) by default, plus optional opt-ins for the error-handler stub and rate-limit primitive, AND registers each in every configured env's YAML so callers can reference them by ID. For copying just one primitive without registration, see [`copy-primitive.md`](copy-primitive.md).

## How

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/helpers/create_lock.py \
  [--include-error-handler] \
  [--include-rate-limit] \
  [--force-overwrite]
```

## Side effects

- Copies these primitives from `${CLAUDE_PLUGIN_ROOT}/primitives/workflows/` into `<workspace>/n8n-workflows-template/`:
  - `lock_acquisition.template.json` (always)
  - `lock_release.template.json` (always)
  - `error_handler_lock_cleanup.template.json` (with `--include-error-handler`)
  - `rate_limit_check.template.json` (with `--include-rate-limit`)
- Registers each in every configured env's YAML (delegates to `create_workflow.py --no-template`). This mints placeholder workflow IDs that callers reference via `{{@:env:workflows.lock_acquisition.id}}` etc.
- Adds them to `deployment_order.yml` under "Tier 0a: leaves" so they deploy before any caller workflow that depends on them.

After this skill, the user owns the primitives in their workspace. The harness's seed copies in `${CLAUDE_PLUGIN_ROOT}/primitives/workflows/` are never written to.

## What you're actually deploying

The four primitives are sub-workflows that wrap the dedicated `n8n-nodes-base.redis` node:

- `lock_acquisition` uses Redis-native atomic INCR + EXPIRE for acquire, with a GET-poll wait loop for retry-on-contention. 13 nodes total.
- `lock_release` does a plain Redis DEL. 4 nodes.
- `error_handler_lock_cleanup` is a no-op stub — orphans self-heal via Redis-side EXPIRE.
- `rate_limit_check` is a fixed-window INCR counter, 4 nodes.

For node-graph diagrams + the Redis key namespace, see [`skills/integrations/redis/lock-pattern.md`](integrations/redis/lock-pattern.md). For the safety model (atomic INCR prevents race-on-acquire) and when this pattern is NOT safe enough (multi-region Redis, fairness-required), see [`skills/patterns/locking.md`](patterns/locking.md).

| Primitive | Used by |
|---|---|
| `lock_acquisition` + `lock_release` | `add-lock-to-workflow.md` (the standard wrap-a-workflow flow) |
| `error_handler_lock_cleanup` | `add-lock-to-workflow.md --lock-on-error` (currently a no-op stub; orphans clean up via TTL) |
| `rate_limit_check` | `add-rate-limit-to-workflow.md` |

## Flag details

- **`--include-error-handler`** — also copy `error_handler_lock_cleanup`. Required if you'll add `--lock-on-error` to any workflow via `add-lock-to-workflow`.
- **`--include-rate-limit`** — also copy `rate_limit_check`. Required before `add-rate-limit-to-workflow` will run.
- **`--force-overwrite`** — overwrite existing workspace copies of the primitives instead of skipping them. Default off (preserves idempotence). Without the flag, an already-present primitive triggers:
  ```
  WARNING: <key>.template.json already exists — re-run with --force-overwrite
  to update to the real Redis implementation.
  ```
  Use this when upgrading from an earlier harness version that shipped placeholder Set-node primitives — it pulls the current real-Redis bodies in.

## Next steps

- [`add-lock-to-workflow.md`](add-lock-to-workflow.md) to wrap a workflow's flow in lock acquire / release.
- [`add-rate-limit-to-workflow.md`](add-rate-limit-to-workflow.md) to gate a workflow with a rate-limit (requires `--include-rate-limit` here).

## When to use copy-primitive instead

Use [`copy-primitive.md`](copy-primitive.md) instead of this skill when:
- You only want one primitive, not the bundled lock pair.
- You don't need env-YAML registration (e.g., experimenting in a fresh workspace before bootstrap-env).
- You want to force-update one primitive without touching the others.

`create-lock` is "everything for locking, ready to deploy". `copy-primitive` is "drop one file in".
