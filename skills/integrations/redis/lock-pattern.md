---
name: integration-redis
description: Redis-backed coordination primitives — atomic-INCR lock with GET-poll wait loop, rate-limit, key namespace.
user-invocable: false
---

# Redis (lock + rate-limit pattern)

The harness ships four primitives backed by the dedicated `n8n-nodes-base.redis` node (NOT `this.helpers.redis.call(...)` from a Code node — that API is only exposed inside custom-node `INodeType.execute()` methods, not in user Code-node sandboxes).

## Credential

`redis` credential type. See [`skills/manage-credentials.md`](../../manage-credentials.md). The four primitives all reference it via `{{@:env:credentials.redis.{id,name}}}` placeholders.

## Shipped primitives

| Primitive | Trigger | Output |
|---|---|---|
| `lock_acquisition` | `executeWorkflowTrigger` (inputs: `scope, ttl_seconds, execution_id, wait_till_lock_released, max_wait_seconds`) | `{ acquired, count, scope, lock_id, key }` |
| `lock_release` | `executeWorkflowTrigger` (inputs: `scope`) | `{ released: true, scope }` |
| `error_handler_lock_cleanup` | `errorTrigger` | `{ cleaned: false, reason, executionId }` (no-op stub; TTL handles cleanup) |
| `rate_limit_check` | `executeWorkflowTrigger` (inputs: `scope, limit, windowSeconds`) | `{ allowed, scope, count, limit }` |

Every Code-node body inside these primitives starts with `// @n8n-harness:primitive` to bypass `validate.py`'s pure-function discipline. **Do not copy that marker into user Code nodes** — it silently disables validation.

## Lock value: just an integer

The lock value at the Redis key `lock-<scope>` is a plain integer counter (Redis-native semantics). The first caller's INCR creates the key with value 1; concurrent callers' INCRs return 2, 3, …. Whoever sees `count === 1` holds the lock.

There is no JSON metadata stored in Redis — earlier B-9-era versions stored `{ lock_id, workflow_id, ... }` for client-side stale-check, but with INCR the staleness check moved to Redis itself (server-side EXPIRE), so the metadata is unnecessary for correctness. The `lock_id` returned to the caller is set to `execution_id` in the primitive's `Build Lock Context` Code node, useful for caller-side correlation but not stored in Redis.

## `lock_acquisition` node graph (13 nodes)

```
Execute Workflow Trigger
       │
       ▼
Build Lock Context (Code: scope, ttl, executionId, key, deadline_ms = now + max_wait_seconds*1000)
       │
       ▼
INCR Acquire Attempt (Redis INCR + EXPIRE)  ◄────────────────────────────┐
       │                                                                  │
       ▼                                                                  │
Evaluate Acquired (Code: count = $json[ctx.key]; acquired = count === 1)  │
       │                                                                  │
       ▼                                                                  │
Acquired? (If $json.acquired === true)                                    │
   ├── true  → (success — flow ends, output = Evaluate Acquired's payload)│
   └── false → Should Wait? (If wait_till_lock_released === true)         │
                  ├── false → Fail Fast — Lock Held (Stop and Error)      │
                  └── true  → Wait Before Poll (n8n Wait, 1 second)       │
                               │                                          │
                               ▼                                          │
                              GET Lock (Redis GET, propertyName=LOCK_VALUE)
                               │                                          │
                               ▼                                          │
                              Check Wait State (Code: returns state ∈     │
                                {timeout, retry-incr, keep-waiting})      │
                               │                                          │
                               ▼                                          │
                              Timeout? (If state === 'timeout')           │
                               ├── true  → Wait Timeout — Stop (Stop and Error)
                               └── false → Retry INCR? (If state === 'retry-incr')
                                              ├── true  ───────────────── ┘
                                              └── false → loops back to Wait Before Poll
```

Node-by-node:

- **Build Lock Context**: pure JS. Computes `key = lock-<scope>`, `lock_id = executionId`, `deadline_ms = Date.now() + max_wait_seconds * 1000`. Output is referenced via `$('Build Lock Context').first().json` from every loop iteration — n8n's `$()` returns the most recent execution of a node, which is stable across loop revisits.
- **INCR Acquire Attempt**: Redis INCR with `expire: true, ttl: $json.ttl`. INCR is atomic server-side; only one concurrent caller sees the post-increment count of 1. EXPIRE is re-applied on every INCR (a property of the n8n Redis node) — not a problem for the holder (their TTL gets refreshed each time someone else races and fails) and bounded by max_wait_seconds for waiters.
- **Evaluate Acquired**: pure JS. Reads `$json[ctx.key]` (the INCR result) and computes `acquired = count === 1`.
- **Acquired?**: standard If. Success branch is empty `[]` — n8n returns the `Evaluate Acquired` payload as the workflow output when the flow terminates here.
- **Should Wait?**: routes between fail-fast (Stop and Error) and wait-loop based on the original `wait_till_lock_released` input.
- **Wait Before Poll**: n8n Wait node, `amount: 1, unit: seconds`. Releases the worker between polls (not pinned).
- **GET Lock**: Redis GET with `propertyName: LOCK_VALUE`. Read-only — does NOT touch the EXPIRE. Returns null if the key has expired or been DEL'd.
- **Check Wait State**: pure JS. Reads `$json.LOCK_VALUE` and `Build Lock Context`'s `deadline_ms`. Returns one of three states:
  - `timeout` if `now > deadline_ms`
  - `retry-incr` if `LOCK_VALUE` is null/empty (lock released — try INCR again)
  - `keep-waiting` if `LOCK_VALUE` is present and not yet timed out
- **Timeout?** + **Retry INCR?**: two sequential If nodes routing on the state field.

### Why GET, not INCR, in the wait loop

Re-INCR'ing inside the wait loop would re-EXTEND the EXPIRE TTL on every poll attempt (the n8n Redis node always re-applies EXPIRE on INCR), defeating the holder's TTL backstop. GET is read-only and doesn't touch the TTL — so the holder's TTL counts down independently of how many waiters are polling.

### Wasted INCRs on re-race

If 5 waiters all see GET=null and all simultaneously re-INCR:
- Caller A: post-increment value 1 → acquired
- Callers B/C/D/E: values 2–5 → re-enter wait

The wasted INCRs leave the Redis counter at 5 instead of 1. **Harmless** — `count === 1` is the ownership check (only A holds), and when A eventually DELs on release, the inflated counter goes with the key. The next acquire INCRs from scratch.

## `lock_release` node graph (4 nodes)

```
Execute Workflow Trigger ──► Build Lock Key (Code: scope, key) ──► DEL Lock (Redis DEL) ──► Build Result (Code)
```

Output: `{ released: true, scope }`. Idempotent on absent key (Redis DEL returns 0 if the key didn't exist; the workflow doesn't care).

No ownership check. The wrapper flow (`add_lock_to_workflow.py`) ensures only the lock holder reaches release — failed acquires Stop and Error before the critical section, so they never call release. A defensive ownership check would protect against caller bugs that don't happen in normal use.

## `rate_limit_check` node graph (4 nodes)

```
Execute Workflow Trigger
       │
       ▼
Build Bucket Key (Code: scope/limit/windowSeconds + key = ratelimit-<scope>-<bucket>)
       │
       ▼
Redis INCR (operation=incr, key=$json.key, expire=true, ttl=$json.windowSeconds)
       │
       ▼
Build Result (Code: count = $json[prev.key]; allowed = count <= prev.limit)
       │
       ▼ output: { allowed, scope, count, limit }
```

Bucket key: `ratelimit-<scope>-<floor(now_ms / (windowSeconds * 1000))>`. The bucket integer rotates each window, so old buckets garbage-collect via their own EXPIRE TTL.

Boundary-burst caveat: a caller can hit `limit` near the end of one window and `limit` again at the start of the next, so observed throughput can reach `2 × limit` across the edge. Token-bucket would smooth this but is deferred.

## `error_handler_lock_cleanup` (no-op stub, 2 nodes)

```
Error Trigger ──► TTL Bounded Cleanup (Code: returns { cleaned: false, reason, executionId })
```

No Redis ops. Orphaned locks self-heal via Redis-side EXPIRE — when a workflow holds the lock and crashes before reaching `lock_release`, the EXPIRE counts down from the original acquire time and the key vanishes after `ttl_seconds`. The next `lock_acquisition` INCR sees the key absent and starts fresh.

To upgrade to active cleanup later, replace the stub with: Redis EXISTS at the failed scope's key → If present → Redis DEL. Much simpler than the B-9-era token-fencing version.

## Key namespace

| Key shape | Operation | Set by | Cleared by |
|---|---|---|---|
| `lock-<scope>` (e.g. `lock-excel-fileId-123`) | Plain integer counter | `lock_acquisition.INCR Acquire Attempt` (INCR + EXPIRE) | `lock_release.DEL Lock` (DEL) OR Redis EXPIRE after `ttl_seconds` |
| `ratelimit-<scope>-<bucket>` | Rate-limit counter | `rate_limit_check.Redis INCR` (INCR + EXPIRE) | EXPIRE after `windowSeconds` |

`<bucket>` for rate-limit is `floor(Date.now() / (windowSeconds * 1000))` — an integer that increments once per window.

## TTL discipline

- **Lock TTL** defaults to `86400` (24h). Set on Redis at acquire-time via INCR's `expire: true, ttl: <n>` parameter. **Server-enforced.** A crashed holder's lock auto-expires after `ttl_seconds`.
- **`max_wait_seconds`** also defaults to `86400` (24h). Different concept: this is the wait-loop's deadline (how long a waiter polls before giving up). Override per-workflow for time-sensitive callers (webhooks → 30s).
- **Rate-limit TTL** equals `windowSeconds`, applied via the Redis INCR node's `expire: true, ttl: ...` parameters. Server-enforced.

## Why `this.helpers.redis` is NOT used

n8n Code nodes run inside a V8 isolate that exposes only `$json`, `$input`, `$()`, `$node`, `$execution`, `$workflow`, `$now`, `$today`. The `this.helpers.*` API surface (httpRequest, redis, etc.) is the **node-developer SDK** — accessible only from `INodeType.execute()` in custom-node code, NOT from the user-facing Code-node sandbox. n8n's docs hedge this: "Some methods and variables aren't available in the Code node. These aren't in the documentation."

So all Redis I/O in the harness primitives goes through the dedicated `n8n-nodes-base.redis` node. The Code nodes only do pure JS work (key construction, count comparison, deadline arithmetic, state-routing decisions).

## See also

- [`skills/patterns/locking.md`](../../patterns/locking.md) — atomic-INCR safety model, when this pattern is + isn't safe.
- [`skills/manage-credentials.md`](../../manage-credentials.md) — Redis credential setup.
- [`skills/create-lock.md`](../../create-lock.md) — installing the lock pair into a workspace.
- [`skills/copy-primitive.md`](../../copy-primitive.md) — copy any single primitive without bundled registration.
- [`skills/add-lock-to-workflow.md`](../../add-lock-to-workflow.md) — wrap an existing workflow with acquire/release.
- [`skills/add-rate-limit-to-workflow.md`](../../add-rate-limit-to-workflow.md) — gate a workflow with rate-limit.
