---
id: bare-equals-scope-auto-wrapped
category: edge-case
difficulty: easy
---

# Bare-`=` scope expression — auto-wrapped with deprecation warning

## Prompt

> "Add a lock to `tenant_provisioning` with scope per-tenant: `--scope-expression \"='tenant-' + \$json.tenantId\"`."

(Note the bare-`=` form — pre-task-12 this silently broke.)

## Expected skills consulted

1. `skills/add-lock-to-workflow.md` (the canonical-form warning section)

## Expected helpers invoked

1. `helpers/add_lock_to_workflow.py --workflow-key tenant_provisioning --scope-expression "='tenant-' + \$json.tenantId" --ttl-seconds 600`

## Expected artifacts

- `n8n-workflows-template/tenant_provisioning.template.json` updated with Lock Acquire / Release nodes whose `workflowInputs.value.scope` is `={{ 'tenant-' + $json.tenantId }}` (auto-wrapped to canonical form).

## Expected state changes

None until deploy.

## Success criteria

- [ ] Helper prints `WARNING: --scope-expression normalized to canonical form: "={{ 'tenant-' + $json.tenantId }}"`.
- [ ] Deployed workflow's Lock Acquire scope evaluates correctly under contention — concurrent calls with different `tenantId`s run in parallel, same `tenantId` serializes.

## Pitfalls

- **Pre-task-12 behavior** (legacy bug): bare-`=` was treated as a literal string by `executeWorkflow@1.2`'s `defineBelow` mode. Per-resource scopes silently degraded to a single global lock keyed on the literal expression text. Two callers with different payloads hit the same lock.
- **Post-task-12 behavior** (current): `_normalize_n8n_expression` auto-wraps `=<expr>` to `={{ <expr> }}` and emits a one-shot deprecation warning. Calling code keeps working; user sees the warning and learns to use canonical form going forward.
- The same normalization applies to `add_rate_limit_to_workflow.py --scope-expression`. The two helpers share the normalizer.
- Empty / None / whitespace-only scope expressions are REJECTED with `ValueError` (no auto-wrap into something silly). Operator must provide a non-empty value or use the default `={{ $execution.id }}`.

## Notes

This was task-12 finding #15 from the lock-concurrency live test. The auto-wrap is friendlier than a hard error, and the deprecation warning is the migration signal.
