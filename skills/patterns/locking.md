---
name: pattern-locking
description: Distributed coordination — fail-fast lock, wait-on-lock, and rate-limit modes built on Redis-backed sub-workflows.
---

# Pattern: locking + rate-limit

A workflow that mutates a shared resource (a Sharepoint Excel file, a database row, an external CMS, …) needs a mutex to prevent two concurrent runs from clobbering each other. A workflow that fronts an API needs a rate-limit so a single caller can't exhaust shared quota. The harness ships four primitive workflows that compose into three modes:

| Mode | Primitive | Caller payload | Returns |
|---|---|---|---|
| Lock — fail-fast | `lock_acquisition` | `{ scope }` | `{ acquired, scope, waitedMs }` |
| Lock — wait-with-timeout | `lock_acquisition` | `{ scope, maxWaitMs, pollIntervalMs?, ttlSeconds? }` | `{ acquired, scope, waitedMs }` |
| Rate limit | `rate_limit_check` | `{ scope, limit, windowSeconds }` | `{ allowed, scope, count, limit }` |

`lock_release` (paired with `lock_acquisition`) and `error_handler_lock_cleanup` (paired with `--lock-on-error`) are operations on the lock primitive, not separate modes.

## Primitives shipped

- **`lock_acquisition`** — Execute Workflow Trigger → Code node calling `this.helpers.redis.call('SET', lockKey, ownerId, 'NX', 'EX', String(ttl))`. With `maxWaitMs > 0`, polls every `pollIntervalMs` until acquired or the deadline passes. On success, also writes a `lock-owner-<executionId>` pointer that the error-handler cleanup uses to resolve the scope.
- **`lock_release`** — Execute Workflow Trigger → Code node calling DEL on both the lock key and the owner pointer. Idempotent (DEL on a missing key is a no-op).
- **`error_handler_lock_cleanup`** — Error Trigger → Code node that GETs `lock-owner-<failedExecutionId>` (resolved via `$workflow.errorData.execution.id`), DELs the lock + owner pointer if present.
- **`rate_limit_check`** — Execute Workflow Trigger → Code node calling `INCR ratelimit-<scope>-<bucket>`, EXPIRE on first INCR per bucket. Returns `{ allowed, scope, count, limit }`.

Each Code-node body opens with `// @n8n-harness:primitive` so `validate.py` exempts it from the pure-function discipline rule. **Do not copy that marker into user Code nodes** — it will silently bypass validation. The marker is reserved for harness-shipped primitives only.

## How to wire it in

| Goal | Skill |
|---|---|
| Install the primitives in the workspace | [`create-lock.md`](../create-lock.md) — use `--include-error-handler` and/or `--include-rate-limit` as needed. |
| Wrap a workflow in lock acquire / release | [`add-lock-to-workflow.md`](../add-lock-to-workflow.md) |
| Wrap a workflow in lock acquire / release **with wait** | [`add-lock-to-workflow.md`](../add-lock-to-workflow.md) — pass `--max-wait-ms` |
| Add error-handler cleanup so a crashed workflow releases its lock | [`add-lock-to-workflow.md`](../add-lock-to-workflow.md) — pass `--lock-on-error` (requires `--include-error-handler` at create-lock time) |
| Gate a workflow with a rate-limit | [`add-rate-limit-to-workflow.md`](../add-rate-limit-to-workflow.md) — requires `--include-rate-limit` at create-lock time |

## Scope expression

Each primitive invocation passes a `scope` field. Defaults:

- Lock: `={{ $execution.id }}` — "one execution at a time" semantics.
- Rate limit: typically per-caller, e.g. `=api-v1-{{ $json.userId }}`.

For per-resource locking (e.g., one Excel file at a time), use `={{ 'excel-' + $json.fileId }}`. The string becomes the suffix of the Redis key (`lock-<scope>` or `ratelimit-<scope>-<bucket>`), so anything that produces a stable per-protected-thing string works.

## Owner-pointer mechanic (lock + error-handler cleanup)

`lock_acquisition` writes two Redis keys on success:

1. `lock-<scope>` → `<executionId>` (the lock itself).
2. `lock-owner-<executionId>` → `<scope>` (a reverse pointer keyed by execution id).

Both share the same TTL. If the protected workflow crashes before reaching `lock_release`, `error_handler_lock_cleanup` runs:

```javascript
const executionId = $workflow.errorData?.execution?.id || $execution.id;
const scope = await this.helpers.redis.call('GET', `lock-owner-${executionId}`);
if (scope) {
  await this.helpers.redis.call('DEL', `lock-${scope}`);
  await this.helpers.redis.call('DEL', `lock-owner-${executionId}`);
}
```

This works regardless of how the scope was originally computed — even dynamic scopes like `excel-{{ $json.fileId }}` are recoverable, because the owner pointer captures the resolved string.

If both keys somehow leak (the cleanup also crashes), the lock TTL backstops the keyspace — by default 60 s after the original acquire.

## Worker-pinning trade-off (wait mode)

`maxWaitMs > 0` switches `lock_acquisition` to bounded polling: the n8n worker is held for the entire wait. Two consequences:

- A pool of W workers can have at most W concurrent waiters across all locks before saturation.
- A long `maxWaitMs` (10 s+) on a hot lock can serialize unrelated traffic.

Recommendation: keep `--max-wait-ms ≤ 2000` unless you've measured your worker pool. Above that, switch to a queue or smaller scopes instead.

Pub-sub-based wait (no polling, worker released between polls) is intentionally out of scope — bounded polling is the documented trade-off.

## Rate-limit semantics + boundary burst

`rate_limit_check` is **fixed-window INCR**:

- Bucket key: `ratelimit-<scope>-<floor(now_ms / (windowSeconds * 1000))>`.
- INCR returns the new count; EXPIRE is set on the first INCR per bucket so within-window calls don't reset TTL.
- `allowed = count <= limit`.

The boundary burst caveat: a caller can hit `limit` near the end of one window and `limit` again at the start of the next, so the worst-case observed throughput is `2 × limit` across the boundary. Token-bucket would smooth this but is deferred — the simpler INCR semantics are usually sufficient for "throttle obvious abuse" rather than "enforce a strict ceiling".

## Key namespace summary

| Key shape | Purpose |
|---|---|
| `lock-<scope>` | The mutex itself (SETNX + EX). |
| `lock-owner-<executionId>` | Reverse pointer — lets the error-handler cleanup resolve the scope. |
| `ratelimit-<scope>-<bucket>` | Rate-limit counter for a single fixed window. |

The `<bucket>` integer for rate-limit auto-rotates each window, so old buckets are garbage-collected by their own TTL.

## Caveats

- **Real Redis required.** All four primitives call `this.helpers.redis.call(...)` — a Redis credential must be reachable from your n8n instance. See [`skills/integrations/redis/lock-pattern.md`](../integrations/redis/lock-pattern.md).
- **Single-instance Redis assumed.** Multi-region coordination is out of scope.
- **`$workflow.errorData.execution.id` must be verified against your n8n version.** The error-handler cleanup body uses this path; if wrong, GET returns null and cleanup silently no-ops. The `?.` chain plus `|| $execution.id` fallback prevent a crash. Verify by running a workflow that throws after acquire and inspecting the cleanup output's `cleaned` field.
- **Owner-pointer keyspace growth.** Bounded by `(concurrent_executions × ttlSeconds)` — small under typical loads.
- **No automatic primitive migration.** Workspaces with old placeholder Set-node primitives are not auto-updated. Use `create_lock.py --force-overwrite` to opt in.
