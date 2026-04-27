---
name: add-lock-to-workflow
description: Wrap a workflow's main flow in lock acquire / release Execute Workflow nodes (token-fencing pattern with TTL).
---

# add-lock-to-workflow

## When

An existing workflow needs to wrap its critical section in distributed-lock acquire / release calls so concurrent runs don't clobber each other's shared resource.

## How

```bash
python3 <harness>/helpers/add_lock_to_workflow.py \
  --workflow-key <wf> \
  [--lock-on-error] \
  [--scope-expression "={{ 'excel-' + $json.fileId }}"] \
  [--ttl-seconds 86400] \
  [--fail-fast]
```

## What it does to your template

Edits `<workspace>/n8n-workflows-template/<wf>.template.json` by splicing two `Execute Workflow` nodes around the existing main flow:

```
Trigger ──► Lock Acquire ──► <your existing main flow> ──► Lock Release
```

- `Lock Acquire` calls the `lock_acquisition` sub-workflow with `{ scope, workflow_id, workflow_name, wait_till_lock_released, execution_id, ttl_seconds }`.
- `Lock Release` calls the `lock_release` sub-workflow with `{ lock_id, scope }`. The `lock_id` value is `={{ $('Lock Acquire').item.json.lock_id }}` — n8n threads the acquire-time token through to the release call so the primitive's token-fencing check passes.
- Downstream nodes are shifted right by 440 px to make room.
- With `--lock-on-error`, sets `settings.errorWorkflow` to `error_handler_lock_cleanup` (delegates to `register-workflow-to-error-handler.md`).

Refuses if the lock primitives aren't yet in the workspace — run [`create-lock.md`](create-lock.md) first.

## What the lock primitives actually do

For node-graph diagrams of `lock_acquisition` (10 nodes) and `lock_release` (6 nodes), and the JSON shape stored in Redis, see [`skills/integrations/redis/lock-pattern.md`](integrations/redis/lock-pattern.md). Quick summary:

- **Acquire**: generate UUID → GET the scope key → if absent or stale (locked_at + ttl_seconds < now), SET it with the new lock_id + workflow metadata → return `{ lock_id }`. If held and `wait_till_lock_released` is true, an n8n Wait node fires (releasing the worker) then loops back to GET. If held and false, Stop and Error fires immediately.
- **Release**: GET the scope key → JSON.parse → if stored lock_id matches the caller's, DEL; if mismatch, Stop and Error with details about who really holds the lock. Idempotent on absent key.

## Flag reference

### `--scope-expression "<n8n-expression>"`

The Redis key for the lock. Default: `={{ $execution.id }}` (one-execution-at-a-time semantics).

For per-resource locking pick a stable string per protected thing:
- One Excel file at a time: `="excel-" + $json.fileId`.
- One CMS row at a time: `="cms-" + $json.rowId`.
- Single global lock across all callers: `="global"`.

### `--ttl-seconds <int>`

Default `86400` (24h). The lock value carries this; client-side stale-check evicts expired locks on next contention. Tune per workflow:

- A payment workflow with a 5-minute critical section → `--ttl-seconds 600` (10 min, generous buffer).
- A long batch job that may run for 6 hours → `--ttl-seconds 32400` (9h, also generous).

The TTL is NOT a wait timeout. It bounds how long an orphaned lock blocks the scope after a crash.

### `--fail-fast`

Default off. When set, passes `wait_till_lock_released: false` to the acquire primitive: if the lock is held, the workflow stops with an error message including who holds it. Without this flag, the primitive uses an n8n Wait node and retries.

### `--lock-on-error`

Default off. When set, also sets your workflow's `settings.errorWorkflow` to `error_handler_lock_cleanup`. The cleanup primitive is currently a no-op stub (orphan locks rely on TTL); the flag is wired so an upgrade to active cleanup later doesn't require re-running this helper.

## Worked example

```bash
# 1. Make sure the lock pair is in your workspace.
python3 <harness>/helpers/create_lock.py

# 2. Wrap your workflow with a 10-minute TTL, scoping per Excel file.
python3 <harness>/helpers/add_lock_to_workflow.py \
  --workflow-key sharepoint_writeback \
  --scope-expression "='excel-' + $json.fileId" \
  --ttl-seconds 600
```

The result on the wire:

```
Webhook → Lock Acquire (scope=excel-<fileId>, ttl=600) → ... your writeback nodes ... → Lock Release (lock_id from Acquire)
```

Two simultaneous webhooks for the same `fileId` race at Lock Acquire. The first wins; the second waits at the n8n Wait node, then retries until the first releases. Two webhooks for *different* `fileId`s acquire independent locks — no contention.

## Pattern + caveats

See [`skills/patterns/locking.md`](patterns/locking.md) for:
- The token-fencing safety model (race-on-acquire is detectable on release, not prevented).
- TTL semantics + bounded-leak behavior.
- When NOT to use this (financial transactions, irreversible side effects).
- Position-shift heuristic ([position-recalculation](patterns/position-recalculation.md)).
