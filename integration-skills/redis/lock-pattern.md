# Redis: lock pattern

## Node type

- `n8n-nodes-base.redis` — SET / GET / EXPIRE / DEL / etc.

## Credential block

```json
"credentials": {
  "redis": {
    "id": "{{HYDRATE:env:credentials.redis.id}}",
    "name": "{{HYDRATE:env:credentials.redis.name}}"
  }
}
```

## Lock acquire/release pattern

The existing `lock_acquiring`, `lock_releasing`, and `error_handler_lock_cleanup` workflows in `dev.yaml` implement this. Caller flow:

1. Execute Workflow → `lock_acquiring` (with key, ttl)
2. Critical section (do the work)
3. Execute Workflow → `lock_releasing` (with same key)
4. Set `errorWorkflow` to `error_handler_lock_cleanup` so a crash still releases the lock.

`lock_acquiring` does:

```json
{
  "type": "n8n-nodes-base.redis",
  "parameters": {
    "operation": "set",
    "key": "lock:{{ $json.lockKey }}",
    "value": "1",
    "expire": true,
    "ttl": 600,
    "set": "ifNotExist"
  }
}
```

Note the `set: "ifNotExist"` — that's `SETNX` semantics. If the key exists, the SET fails and the workflow can branch to "wait" or "fail fast".

## Common quirks

- **TTL is mandatory.** A bug in the workflow that crashes between acquire and release will leak a lock forever without TTL. Always set a TTL even if you also have an error-handler — defense in depth.
- **Key prefix.** Use a workflow-specific prefix (`lock:invoice-pipeline:` not just `lock:`) to avoid collisions across workflows.
- **JSON values.** Redis SET stores strings. To store JSON, stringify in a Code node first; on GET, parse it back.

## Worked example

`po_reconciliation_pipeline.template.json` (in this repo) uses the lock pattern around its Excel + Gmail processing. The lock key is the SAP export filename so two pipelines processing the same file don't overlap.
