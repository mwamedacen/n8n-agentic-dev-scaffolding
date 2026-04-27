---
name: integration-redis
description: Redis nodes — distributed lock recipe via Code-node + this.helpers.redis with SETNX + TTL.
---

# Redis (lock pattern)

## Node type

The harness ships its lock primitives as `n8n-nodes-base.code` nodes that call `this.helpers.redis.call(...)` directly. The dedicated `n8n-nodes-base.redis` node is fine for ad-hoc ops, but the primitives need atomic SETNX with TTL — the Code-node surface is the correct place.

## Credential type

`redis`.

For the actual setup flow, see [`skills/manage-credentials.md`](../../manage-credentials.md). Path A works well — Redis credentials are usually a single host/port/password tuple in `.env.<env>`.

## Shipped primitives (real bodies)

The harness ships three lock primitives at `<harness>/primitives/workflows/`:

- `lock_acquisition.template.json` — fail-fast or wait-with-timeout mutex.
- `lock_release.template.json` — release the lock + owner pointer.
- `error_handler_lock_cleanup.template.json` — clean up after a crashed execution.

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

## TTL discipline

- Lock TTL defaults to 60s; tune via `--ttl-seconds` per workload.
- Owner pointer shares the lock TTL — both expire together if the execution crashes without releasing.

## Key namespace

| Key shape | Purpose | Owner |
|---|---|---|
| `lock-<scope>` | The mutex itself | `lock_acquisition` (SETNX), `lock_release` (DEL), `error_handler_lock_cleanup` (DEL) |
| `lock-owner-<executionId>` | Reverse pointer for error-handler cleanup | `lock_acquisition` (SET on success) |

## See also

- [`skills/patterns/locking.md`](../../patterns/locking.md) for the lock pattern (when to use, scope expressions).
- [`skills/manage-credentials.md`](../../manage-credentials.md) for credential setup.
