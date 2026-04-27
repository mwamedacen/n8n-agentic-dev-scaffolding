---
name: integration-redis
description: Redis-backed coordination primitives — lock acquire/release node graphs, rate-limit, lock-value JSON shape, key namespace.
---

# Redis (lock + rate-limit pattern)

The harness ships four primitives backed by the dedicated `n8n-nodes-base.redis` node (NOT `this.helpers.redis.call(...)` from a Code node — that API is only exposed inside custom-node `INodeType.execute()` methods, not in user Code-node sandboxes).

## Credential

`redis` credential type. See [`skills/manage-credentials.md`](../../manage-credentials.md). The four primitives all reference it via `{{HYDRATE:env:credentials.redis.{id,name}}}` placeholders.

## Shipped primitives

| Primitive | Trigger | Output |
|---|---|---|
| `lock_acquisition` | `executeWorkflowTrigger` (inputs: `scope, workflow_id, workflow_name, wait_till_lock_released, execution_id, ttl_seconds`) | `{ lock_id }` |
| `lock_release` | `executeWorkflowTrigger` (inputs: `lock_id, scope`) | `{}` (or fails with LOGIC ERROR) |
| `error_handler_lock_cleanup` | `errorTrigger` | `{ cleaned: false, reason, executionId }` (no-op stub; TTL handles cleanup) |
| `rate_limit_check` | `executeWorkflowTrigger` (inputs: `scope, limit, windowSeconds`) | `{ allowed, scope, count, limit }` |

Every Code-node body inside these primitives starts with `// @n8n-harness:primitive` to bypass `validate.py`'s pure-function discipline. **Do not copy that marker into user Code nodes** — it silently disables validation.

## Lock value JSON shape

`lock_acquisition`'s `set_lock` Redis SET writes this JSON-stringified payload at `<scope>`:

```json
{
  "lock_id": "<uuid>",                 // crypto.randomUUID() — caller's release token
  "workflow_id": "<wf-id>",            // identity of the workflow that acquired
  "workflow_name": "<wf-name>",        // human-readable
  "execution_id": "<exec-id>",         // n8n execution that holds it
  "locked_at": "<iso-8601>",           // when the SET happened
  "ttl_seconds": 86400                 // how long this caller considers the lock valid
}
```

The `ttl_seconds` field travels in the value (not in a Redis-side EXPIRE) because n8n's Redis v1 `set` operation has no `expire` parameter (verified against the official TS types). TTL is enforced client-side: `parse_and_check_lock` in the acquire flow computes `(now - locked_at) > ttl_seconds * 1000` and treats stale locks as released.

## `lock_acquisition` node graph (10 nodes)

```
Execute Workflow Trigger
       │
       ▼
generate_lock_id (Code: crypto.randomUUID())
       │
       ▼
get_lock (Redis GET, propertyName=SCOPE_LOCK)  ◄─────────┐
       │                                                  │
       ▼                                                  │
parse_and_check_lock (Code: JSON.parse + stale-check)     │
       │                                                  │
       ▼                                                  │
If_lock_held ─── false ──► set_lock (Redis SET)           │
       │                       │                          │
       │                       ▼                          │
       │                  set_lock_id (Set: { lock_id })  │
       │                       │                          │
       │                       ▼ (output)                 │
       │                                                  │
       └─── true  ──► If_should_wait_or_fail              │
                            │                             │
                  ┌── true ─┴── false ─┐                  │
                  │                    │                  │
                  ▼                    ▼                  │
       wait_before_retry…    fail_lock_held               │
       (n8n Wait node:       (Stop and Error              │
        releases the          with held-by details)       │
        worker, then          │                           │
        loops back)           ▼                           │
              │             (terminal, errors out)        │
              └─────────────────────────────────────────────┘  (back to get_lock)
```

Node-by-node:

- **generate_lock_id**: Code node. Uses `require('crypto').randomUUID()` to mint the per-acquire token.
- **get_lock**: Redis GET with `propertyName: SCOPE_LOCK`, key from `={{ $('Execute Workflow Trigger').item.json.scope || "SCOPE_LOCK" }}`. Returns `null` if absent.
- **parse_and_check_lock**: Code node. Reads `$json.SCOPE_LOCK`. Parses JSON. Computes `has_active_lock = key_present && value_parses && (now - locked_at) <= ttl_seconds * 1000`. Legacy non-JSON values are treated as held (conservative). Output: `{ has_active_lock, parsed_lock, raw_value }`.
- **If_lock_held**: tests `={{ $json.has_active_lock }}` with operator `boolean.false` → branch [0] is "no active lock" (false), branch [1] is "lock held" (true).
- **set_lock**: Redis SET with the JSON value above. No NX, no EX (the node doesn't expose them).
- **set_lock_id**: Set node returning `{ lock_id }` to the caller.
- **If_should_wait_or_fail**: tests `={{ $('Execute Workflow Trigger').item.json.wait_till_lock_released !== false }}`. True (default) → wait branch. False → fail branch.
- **wait_before_retry_lock_acquisition**: n8n Wait node (default duration). The Wait node releases the worker between checks (no worker-pinning), then resumes and loops back to `get_lock`.
- **fail_lock_held**: Stop and Error with a message including the holding workflow's id/name/execution and `locked_at`.

## `lock_release` node graph (6 nodes)

```
Execute Workflow Trigger
       │
       ▼
get_lock (Redis GET, propertyName=LOCK_VALUE)
       │
       ▼
parse_lock_value (Code, runOnceForEachItem):
   - absent key → is_match: true, already_released: true
   - JSON value → parse + compare lock_id
   - legacy string → coerce to legacy lock object
       │
       ▼
If (tests $json.is_match):
   ├── true  ──► delete_lock (Redis DEL)
   └── false ──► Stop and Error
                 (LOGIC ERROR: lock held by …, not by your lock_id)
```

Idempotent on absent key: a release-after-already-released succeeds silently. The LOGIC ERROR fires only when the key exists AND the stored `lock_id` doesn't match the caller's — i.e. the release came from the wrong holder.

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

No Redis ops. Orphaned locks self-heal via the client-side TTL check in `lock_acquisition.parse_and_check_lock` — any new acquire on the same scope after `locked_at + ttl_seconds` will overwrite the stale value. Trade-off: between failure and next-contention there's a window of `ttl_seconds` where the lock key sits stale in Redis. Tune `--ttl-seconds` per workflow.

To upgrade to active cleanup later, replace the stub with: GET the lock at the failed scope → JSON.parse → check `execution_id` matches `$workflow.errorData?.execution?.id` → DEL if match. Requires either iterating `lock-*` keys (Redis `keys` op) or maintaining an owner-pointer pattern.

## Key namespace

| Key shape | Operation | Set by | Cleared by |
|---|---|---|---|
| `<scope>` (e.g. `excel-fileId-123`, or default `SCOPE_LOCK`) | Lock value (JSON-stringified) | `lock_acquisition.set_lock` (SET) | `lock_release.delete_lock` (DEL) OR overwritten by next acquire after TTL |
| `ratelimit-<scope>-<bucket>` | Rate-limit counter | `rate_limit_check.Redis INCR` (INCR + EXPIRE) | EXPIRE TTL = `windowSeconds` |

`<bucket>` for rate-limit is `floor(Date.now() / (windowSeconds * 1000))` — an integer that increments once per window.

## TTL discipline

- **Lock TTL** defaults to `86400` (24h). Override via `add-lock-to-workflow.py --ttl-seconds`. Pick a value larger than your worst-case critical-section runtime.
- **Lock TTL is client-side**: stored in the lock JSON, evaluated in `parse_and_check_lock`. The Redis key itself never has a server-side EXPIRE on the lock (`set` op doesn't support it).
- **Rate-limit TTL** equals `windowSeconds`, applied via the Redis INCR node's `expire: true, ttl: ...` parameters. Server-enforced.

## Why `this.helpers.redis` is NOT used

n8n Code nodes run inside a V8 isolate that exposes only `$json`, `$input`, `$()`, `$node`, `$execution`, `$workflow`, `$now`, `$today`. The `this.helpers.*` API surface (httpRequest, redis, etc.) is the **node-developer SDK** — accessible only from `INodeType.execute()` in custom-node code, NOT from the user-facing Code-node sandbox. n8n's docs hedge this: "Some methods and variables aren't available in the Code node. These aren't in the documentation."

So all Redis I/O in the harness primitives goes through the dedicated `n8n-nodes-base.redis` node. The Code nodes only do pure JS work (UUID generation, JSON parse/stringify, stale-check arithmetic).

## See also

- [`skills/patterns/locking.md`](../../patterns/locking.md) — fail-fast vs wait modes, token-fencing safety model, when this pattern is NOT safe enough.
- [`skills/manage-credentials.md`](../../manage-credentials.md) — Redis credential setup.
- [`skills/create-lock.md`](../../create-lock.md) — installing the lock pair into a workspace.
- [`skills/copy-primitive.md`](../../copy-primitive.md) — copy any single primitive without bundled registration.
- [`skills/add-lock-to-workflow.md`](../../add-lock-to-workflow.md) — wrap an existing workflow with acquire/release.
- [`skills/add-rate-limit-to-workflow.md`](../../add-rate-limit-to-workflow.md) — gate a workflow with rate-limit.
