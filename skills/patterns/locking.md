---
name: pattern-locking
description: Distributed coordination via Redis sub-workflows — token-fencing lock with TTL + fixed-window rate-limit. Architectural rationale, safety model, when NOT to use.
---

# Pattern: locking + rate-limit

A workflow that mutates a shared resource (a Sharepoint Excel file, a database row, an external CMS, …) needs a mutex to prevent two concurrent runs from clobbering each other. A workflow that fronts an API needs rate-limiting to keep one caller from exhausting shared quota. The harness ships four primitives that compose into three operations:

| Mode | Primitive | Caller payload | Returns |
|---|---|---|---|
| Lock — wait-with-retry (default) | `lock_acquisition` | `{ scope, workflow_id, workflow_name, wait_till_lock_released: true, execution_id, ttl_seconds }` | `{ lock_id }` |
| Lock — fail-fast | `lock_acquisition` | `{ scope, workflow_id, workflow_name, wait_till_lock_released: false, execution_id, ttl_seconds }` | `{ lock_id }` OR Stop and Error |
| Rate limit | `rate_limit_check` | `{ scope, limit, windowSeconds }` | `{ allowed, scope, count, limit }` |

`lock_release` is the partner to `lock_acquisition` (always called once per acquire). `error_handler_lock_cleanup` is a no-op stub — orphan locks self-heal via TTL (see below).

For node-graph diagrams + the lock-value JSON shape + the Redis key namespace, see [`skills/integrations/redis/lock-pattern.md`](../integrations/redis/lock-pattern.md).

## Architectural rationale

The straightforward way to build a distributed mutex is `SET key value NX EX ttl` — atomic set-if-not-exists with TTL. n8n provides this neither way:

1. **Code nodes don't expose `this.helpers.redis`**. That API is only available inside custom-node `execute()` methods, not in the user-facing sandbox.
2. **The dedicated `n8n-nodes-base.redis` SET op has no NX flag and no EX param**. Confirmed via the official TS types: `set` accepts only `key | value | keyType | valueIsJSON`.

So a "real" SETNX-EX mutex isn't available without writing a custom n8n node. The harness uses a **token-fencing** pattern instead, with TTL enforced **client-side**. This trades atomic prevention for atomic detection, which is acceptable for the use cases the harness targets but not for everything (see "When NOT to use" below).

## Safety model: token fencing

Each acquire mints a fresh `lock_id` (UUID) and stores it inside the lock value alongside the workflow/execution metadata. The contract is:

- **Acquire**: GET → If absent OR stale → SET with new lock_id → return that lock_id.
- **Release**: GET → JSON.parse → check stored lock_id == caller's lock_id → DEL if match, else Stop and Error.

What this gives:

- **Detectable double-acquire.** If two callers both see "no active lock" simultaneously, both SET. The second writer overwrites the first. Both get a `lock_id`. When they release: the first caller's lock_id no longer matches the stored value → its release fires `LOGIC ERROR: Lock held by <other workflow>` → its workflow stops. The second caller's release matches → DEL succeeds.
- **No silent corruption.** A wrong holder cannot silently DEL someone else's lock. The Stop and Error surfaces the conflict immediately.

What it does NOT give:

- **Prevention of double-execution of the critical section.** Both callers' work runs to the point of release. If your critical section (between acquire and release) does irreversible side effects (e.g. charging a card, sending an email), token fencing alone is insufficient — either side may have already committed before the release-time error.

## When NOT to use this

Use a stronger primitive (Postgres advisory locks, a dedicated coordination service, or a custom n8n node that exposes SETNX-EX) for:

- **Financial transactions** where double-execution is unacceptable (e.g. `charge customer`, `transfer funds`).
- **Idempotent-only-by-design APIs** that have no built-in deduplication (no idempotency keys, no upsert).
- **Hard real-time constraints** where the wait-mode polling adds unacceptable latency.

For everything else (cron-driven Excel updaters, scheduled CMS syncs, throttle-the-LLM-API workflows, etc.), the token-fencing + TTL pattern is the right shape.

## TTL semantics

The lock value carries `ttl_seconds` (default `86400` = 24h). Every caller's `parse_and_check_lock` Code node treats a lock as released if `(now - locked_at) > ttl_seconds * 1000` even though the Redis key itself is still there.

What this gives:

- **Bounded leak on crash.** If a workflow acquires and crashes before reaching `lock_release`, the orphaned lock is automatically considered released after `ttl_seconds`. The next caller will overwrite it cleanly.
- **No worker-pinning during wait.** The wait branch uses an n8n Wait node, which releases the worker between polls. A stuck holder doesn't pin a thread on every waiter.

What it doesn't give:

- **Server-side eviction.** The Redis key persists in storage until next contention or manual DEL. This is fine — quiet locks waste no compute, just a few bytes per scope.
- **Sub-second crash recovery.** With the default `86400`s TTL, an orphan blocks the lock for up to 24h. Tune `--ttl-seconds` per workflow: 5 min for payment workflows, 7 days for long batch jobs.

## Wait mode

Default behavior (`wait_till_lock_released: true`): if the lock is held, the n8n Wait node fires for its configured duration (default in the primitive), then the flow loops back to `get_lock`. Repeat until acquired or until the workflow times out.

`--fail-fast` flips `wait_till_lock_released: false`: the primitive immediately stops with a descriptive error including the holding workflow's identity.

The Wait node has a configurable duration; edit the primitive in your workspace to tune. The harness ships with the n8n default.

## Scope expression

Each primitive invocation passes a `scope` field that becomes the Redis key (or key suffix). Choose carefully:

- `={{ $execution.id }}` — "one execution at a time" semantics. Useful for self-throttling.
- `={{ 'excel-' + $json.fileId }}` — per-resource locking (one Excel file at a time).
- `=api-v1-{{ $json.userId }}` — per-caller rate-limiting.
- `={{ 'global' }}` — single global lock or rate-limit across all callers.

Anything that produces a stable, per-protected-thing string works.

## Owner-pointer mechanic (deferred)

An earlier version of this plan used a separate `lock-owner-${executionId}` reverse pointer for error-handler cleanup. The current implementation drops it: TTL handles orphan cleanup, and the lock value's own `execution_id` field carries the owner identity for any future active-cleanup primitive. See `error_handler_lock_cleanup` in the integrations doc for the upgrade path if TTL-bounded cleanup proves insufficient.

## Rate-limit semantics

`rate_limit_check` is **fixed-window INCR**:

- Bucket key: `ratelimit-<scope>-<floor(now_ms / (windowSeconds * 1000))>`.
- INCR returns the new count; EXPIRE is set on every INCR (the dedicated Redis node always re-applies it). Practical impact is tiny — buckets that go inactive mid-window expire `windowSeconds` after their last call instead of after their first.
- `allowed = count <= limit`.

The boundary burst caveat: a caller can hit `limit` near the end of one window and `limit` again at the start of the next, so the worst-case observed throughput is `2 × limit` across the boundary. Token-bucket would smooth this but is deferred — fixed-window INCR is usually sufficient for "throttle obvious abuse" rather than "enforce a strict ceiling".

## Wiring it in

| Goal | Skill |
|---|---|
| Install the lock pair (copy + register in env YAMLs) | [`create-lock.md`](../create-lock.md) — use `--include-error-handler` and/or `--include-rate-limit` as needed. |
| Copy a single primitive without registration | [`copy-primitive.md`](../copy-primitive.md) |
| Wrap a workflow in lock acquire / release (default wait mode) | [`add-lock-to-workflow.md`](../add-lock-to-workflow.md) |
| Wrap a workflow in lock acquire / release with fail-fast | [`add-lock-to-workflow.md`](../add-lock-to-workflow.md) — pass `--fail-fast` |
| Tune the lock TTL | [`add-lock-to-workflow.md`](../add-lock-to-workflow.md) — pass `--ttl-seconds` |
| Add error-handler cleanup hook (currently a TTL-bounded no-op) | [`add-lock-to-workflow.md`](../add-lock-to-workflow.md) — pass `--lock-on-error` (requires `--include-error-handler` at create-lock time) |
| Gate a workflow with a rate-limit | [`add-rate-limit-to-workflow.md`](../add-rate-limit-to-workflow.md) — requires `--include-rate-limit` at create-lock time |

## Caveats

- **Real Redis required.** All four primitives use `n8n-nodes-base.redis` — a Redis credential must be reachable from your n8n instance. See [`skills/integrations/redis/lock-pattern.md`](../integrations/redis/lock-pattern.md).
- **Single-instance Redis assumed.** Multi-region coordination is out of scope.
- **No automatic primitive migration.** Workspaces with old placeholder Set-node primitives are not auto-updated. Use `create_lock.py --force-overwrite` (or `copy_primitive.py --force-overwrite`) to opt in.
- **Token-fencing is not SETNX**, see "Safety model" + "When NOT to use" above before deploying to high-stakes flows.
