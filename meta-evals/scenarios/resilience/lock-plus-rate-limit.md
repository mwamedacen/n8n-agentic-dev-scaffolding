---
id: lock-plus-rate-limit
category: resilience
difficulty: hard
---

# Workflow with both a lock and a rate-limit

## Prompt

> "My `tenant_provisioning` workflow needs (a) one-at-a-time per tenant (lock per tenantId) and (b) at most 5 calls per minute per tenant (rate-limit). Wire both."

## Expected skills consulted

1. `skills/create-lock.md` (with `--include-rate-limit`)
2. `skills/add-lock-to-workflow.md`
3. `skills/add-rate-limit-to-workflow.md`

## Expected helpers invoked

1. `helpers/create_lock.py --include-rate-limit`
2. `helpers/add_rate_limit_to_workflow.py --workflow-key tenant_provisioning --limit 5 --window-seconds 60 --on-denied error --scope-expression "={{ 'tenant-' + \$json.tenantId }}"`
3. `helpers/add_lock_to_workflow.py --workflow-key tenant_provisioning --scope-expression "={{ 'tenant-' + \$json.tenantId }}" --ttl-seconds 600 --max-wait-seconds 30 --fail-fast`
4. `helpers/validate.py --workflow-key tenant_provisioning`
5. `helpers/deploy.py --env dev --workflow-key tenant_provisioning`

## Expected artifacts

- Template wired with rate-limit gate FIRST (right after trigger), then lock acquire, then main flow, then lock release. Order matters: rate-limit cheaply rejects bursts before the lock's wait-loop, saving Redis traffic and caller wait time.

## Expected state changes

- Workflow deployed + activated. Redis hosts both keys: `n8n-ratelimit-tenant-<tenantId>-<bucket>` (bucket counter) and `n8n-lock-tenant-<tenantId>` (lock counter) + `:meta` sidecar.

## Success criteria

- [ ] First 5 calls per minute per tenant pass the gate; 6th hits denied branch (HTTP 500 since `--on-denied error`).
- [ ] Among the allowed-through, only one runs at a time per tenant; concurrent same-tenant fail-fast at the lock acquire (since `--fail-fast`).
- [ ] Different tenants run in parallel.

## Pitfalls

- **Apply rate-limit BEFORE lock**, not after. Rate-limit's denied path terminates cheaply; if the lock comes first, contention waits even for callers about to be rate-limited.
- The two helpers share a `--scope-expression` shape but the canonical Redis key prefixes differ — `n8n-ratelimit-` vs `n8n-lock-`. No collision.
- `--fail-fast` for the lock + `--on-denied error` for the rate-limit gives webhook callers HTTP 500 for both denial paths. Differentiate via `/api/v1/executions` stop-and-error message.
- Both helpers auto-wrap bare-`=` scope expressions with a deprecation warning — write canonical `={{ ... }}` directly.

## Notes

Common production pattern: rate-limit absorbs burst; lock prevents concurrent writes for the slow path. If you only need one, prefer rate-limit (cheaper for the common case).
