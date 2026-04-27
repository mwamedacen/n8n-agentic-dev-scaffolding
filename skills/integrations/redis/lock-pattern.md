---
name: integration-redis
description: Redis nodes — distributed lock recipe with SETNX + TTL.
---

# Redis (lock pattern)

## Node type

`n8n-nodes-base.redis`.

## Credential type

`redis`.

For the actual setup flow, see [`skills/manage-credentials.md`](../../manage-credentials.md). Path A works well — Redis credentials are usually a single host/port/password tuple in `.env.<env>`.

## Lock recipe (SETNX + TTL)

The harness ships generic placeholder lock primitives at `<harness>/primitives/workflows/{lock_acquisition,lock_release}.template.json`. They use a Set node as a no-op placeholder. Replace with real Redis ops to get distributed mutex semantics:

### `lock_acquisition` body (replace the placeholder Set node)

```json
{
  "type": "n8n-nodes-base.redis",
  "parameters": {
    "operation": "set",
    "key": "={{ 'lock-' + $json.scope }}",
    "value": "={{ $execution.id }}",
    "expire": true,
    "ttl": 60,
    "valueIsJSON": false
  },
  "credentials": {
    "redis": {
      "id": "{{HYDRATE:env:credentials.redis.id}}",
      "name": "{{HYDRATE:env:credentials.redis.name}}"
    }
  }
}
```

For true SETNX (set-if-not-exists), use the n8n Redis node's "set" operation with the `nx` option, or fall back to a Code node that runs:

```javascript
const result = await this.helpers.redis.set(`lock-${scope}`, executionId, 'NX', 'EX', 60);
return [{ json: { acquired: result === 'OK' } }];
```

### `lock_release` body

```json
{
  "type": "n8n-nodes-base.redis",
  "parameters": {
    "operation": "delete",
    "key": "={{ 'lock-' + $json.scope }}"
  },
  "credentials": { "redis": { "id": "...", "name": "..." } }
}
```

## TTL discipline

Always set a TTL on the lock key so a crashed workflow eventually releases it. The default 60s is a reasonable starting point; tune per workload.

## See also

- [`skills/patterns/locking.md`](../../patterns/locking.md) for the lock pattern (when to use, scope expressions).
- [`skills/manage-credentials.md`](../../manage-credentials.md) for credential setup.
