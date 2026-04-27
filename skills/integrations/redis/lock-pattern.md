---
name: integration-redis
description: Redis nodes — distributed lock + rate-limit recipes via Code-node + this.helpers.redis.
---

# Redis (lock + rate-limit pattern)

## Node type

The harness ships its primitives as `n8n-nodes-base.code` nodes that call `this.helpers.redis.call(...)` directly. The dedicated `n8n-nodes-base.redis` node is fine for ad-hoc ops, but the primitives need atomic SETNX with TTL and conditional INCR — the Code-node surface is the correct place.

## Credential type

`redis`.

For the actual setup flow, see [`skills/manage-credentials.md`](../../manage-credentials.md). Path A works well — Redis credentials are usually a single host/port/password tuple in `.env.<env>`.

## Shipped primitives (real bodies)

The harness ships four primitives at `<harness>/primitives/workflows/`:

- `lock_acquisition.template.json` — fail-fast or wait-with-timeout mutex.
- `lock_release.template.json` — release the lock + owner pointer.
- `error_handler_lock_cleanup.template.json` — clean up after a crashed execution.
- `rate_limit_check.template.json` — fixed-window INCR rate limiter.

Each Code-node body opens with `// @n8n-harness:primitive` so `validate.py` skips its pure-function discipline checks. Do not copy that marker into user Code nodes.

### `lock_acquisition` body

```javascript
// @n8n-harness:primitive — exempt from pure-function discipline
const scope = $json.scope || 'default';
const maxWaitMs = typeof $json.maxWaitMs === 'number' ? $json.maxWaitMs : 0;
const pollMs = typeof $json.pollIntervalMs === 'number' ? $json.pollIntervalMs : 200;
const ttl = typeof $json.ttlSeconds === 'number' ? $json.ttlSeconds : 60;
const lockKey = `lock-${scope}`;
const ownerKey = `lock-owner-${$execution.id}`;
const ownerId = $execution.id;

const attempt = async () => {
  const result = await this.helpers.redis.call('SET', lockKey, ownerId, 'NX', 'EX', String(ttl));
  return result === 'OK';
};

const start = Date.now();
let acquired = await attempt();
while (!acquired && maxWaitMs > 0 && (Date.now() - start) < maxWaitMs) {
  await new Promise(r => setTimeout(r, pollMs));
  acquired = await attempt();
}

if (acquired) {
  // Write owner pointer so error_handler_lock_cleanup can resolve the scope
  await this.helpers.redis.call('SET', ownerKey, scope, 'EX', String(ttl));
}

const waitedMs = Date.now() - start;
return [{ json: { acquired, scope, waitedMs } }];
```

Output: `{ acquired, scope, waitedMs }`. With `maxWaitMs > 0`, the node polls every `pollIntervalMs` until either it acquires or the deadline passes — the worker is held for that whole window. Keep `maxWaitMs ≤ 2000` unless you have a deep worker pool.

### `lock_release` body

```javascript
// @n8n-harness:primitive — exempt from pure-function discipline
const scope = $json.scope || 'default';
const lockKey = `lock-${scope}`;
const ownerKey = `lock-owner-${$execution.id}`;
await this.helpers.redis.call('DEL', lockKey);
await this.helpers.redis.call('DEL', ownerKey);
return [{ json: { released: true, scope } }];
```

DEL on a non-existent key is a no-op — double-release is safe.

### `error_handler_lock_cleanup` body

```javascript
// @n8n-harness:primitive — exempt from pure-function discipline
const executionId = $workflow.errorData?.execution?.id || $execution.id;
const ownerKey = `lock-owner-${executionId}`;

const scope = await this.helpers.redis.call('GET', ownerKey);
if (scope) {
  const lockKey = `lock-${scope}`;
  await this.helpers.redis.call('DEL', lockKey);
  await this.helpers.redis.call('DEL', ownerKey);
}

return [{ json: { cleaned: !!scope, executionId, scope: scope || null } }];
```

Resolves the failed execution's scope via the owner pointer (`lock-owner-<execId>` → `<scope>`). The `?.` chain plus `|| $execution.id` fallback prevent a crash if `$workflow.errorData` is missing — but if the execution-id path is wrong, GET returns null and cleanup silently no-ops. Verify against your live n8n version by running a workflow that throws after acquire and inspecting the cleanup output's `cleaned` field.

### `rate_limit_check` body

```javascript
// @n8n-harness:primitive — exempt from pure-function discipline
const scope = $json.scope || 'default';
const limit = typeof $json.limit === 'number' ? $json.limit : 10;
const windowSeconds = typeof $json.windowSeconds === 'number' ? $json.windowSeconds : 60;
const key = `ratelimit-${scope}-${Math.floor(Date.now() / (windowSeconds * 1000))}`;

const count = await this.helpers.redis.call('INCR', key);
if (count === 1) {
  await this.helpers.redis.call('EXPIRE', key, String(windowSeconds));
}
const allowed = count <= limit;
return [{ json: { allowed, scope, count, limit } }];
```

Fixed-window: bucket key includes `floor(now_ms / (windowSeconds * 1000))`. EXPIRE only on first INCR so within-window calls don't reset TTL. Boundary-burst caveat: a caller can hit `limit` near the end of one window and `limit` again at the start of the next (up to `2 × limit` across the edge). Token-bucket is deferred.

## TTL discipline

- Lock TTL defaults to 60 s; tune via `--ttl-seconds` per workload.
- Owner pointer shares the lock TTL — both expire together if the execution crashes without releasing.
- Rate-limit window TTL equals `windowSeconds`. The bucket key auto-rotates each window.

## Key namespace

| Key shape | Purpose | Owner |
|---|---|---|
| `lock-<scope>` | The mutex itself | `lock_acquisition` (SETNX), `lock_release` (DEL), `error_handler_lock_cleanup` (DEL) |
| `lock-owner-<executionId>` | Reverse pointer for error-handler cleanup | `lock_acquisition` (SET on success) |
| `ratelimit-<scope>-<bucket>` | Rate-limit counter for fixed window | `rate_limit_check` (INCR + EXPIRE) |

`<bucket>` is `floor(Date.now() / (windowSeconds * 1000))` — an integer that increments once per window.

## See also

- [`skills/patterns/locking.md`](../../patterns/locking.md) — fail-fast, wait, rate-limit modes; when to use each.
- [`skills/manage-credentials.md`](../../manage-credentials.md) — credential setup.
- [`skills/create-lock.md`](../../create-lock.md) — installing the primitives into a workspace.
