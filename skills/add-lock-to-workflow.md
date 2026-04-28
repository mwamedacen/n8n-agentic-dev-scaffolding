---
name: add-lock-to-workflow
description: Wrap a workflow's main flow in lock acquire / release Execute Workflow nodes (atomic-INCR pattern with Redis-side TTL).
user-invocable: false
---

# add-lock-to-workflow

## When

An existing workflow needs to wrap its critical section in distributed-lock acquire / release calls so concurrent runs don't clobber each other's shared resource.

## How

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/helpers/add_lock_to_workflow.py \
  --workflow-key <wf> \
  [--lock-on-error] \
  [--scope-expression "={{ 'excel-' + $json.fileId }}"] \
  [--ttl-seconds 86400] \
  [--max-wait-seconds 86400] \
  [--fail-fast]
```

## What it does to your template

Edits `<workspace>/n8n-workflows-template/<wf>.template.json` by splicing two `Execute Workflow` nodes around the existing main flow:

```
Trigger ──► Lock Acquire ──► <your existing main flow> ──► Lock Release
```

- `Lock Acquire` calls the `lock_acquisition` sub-workflow with `{ scope, ttl_seconds, execution_id, wait_till_lock_released, max_wait_seconds }`.
- `Lock Release` calls the `lock_release` sub-workflow with `{ scope }`.
- Downstream nodes are shifted right by 440 px to make room.
- With `--lock-on-error`, sets `settings.errorWorkflow` to `error_handler_lock_cleanup` (delegates to `register-workflow-to-error-handler.md`).

Refuses if the lock primitives aren't yet in the workspace — run [`create-lock.md`](create-lock.md) first.

## What the lock primitives actually do

For node-graph diagrams of `lock_acquisition` (13 nodes, includes the wait-loop) and `lock_release` (4 nodes), see [`skills/integrations/redis/lock-pattern.md`](integrations/redis/lock-pattern.md). Quick summary:

- **Acquire**: build context (key, deadline_ms) → atomic Redis INCR with EXPIRE → check `count === 1` → if true, return `{ acquired:true, count, scope, lock_id, key }`. If false (lock held), branch on `wait_till_lock_released`: fail-fast Stop and Error, OR enter a wait loop (Wait 1s → GET → if released re-INCR, else if deadline elapsed Stop and Error, else loop back to Wait).
- **Release**: build key → Redis DEL → return `{ released:true, scope }`. Idempotent on absent key.

The acquire output's `lock_id` field equals the calling workflow's `$execution.id`. It's surfaced for caller-side correlation/logging but isn't used by `lock_release` — release just DELs the key.

## Flag reference

### `--scope-expression "<n8n-expression>"`

The Redis key suffix for the lock. Default: `={{ $execution.id }}` (one-execution-at-a-time semantics).

For per-resource locking pick a stable string per protected thing:
- One Excel file at a time: `="excel-" + $json.fileId`.
- One CMS row at a time: `="cms-" + $json.rowId`.
- Single global lock across all callers: `="global"`.

### `--ttl-seconds <int>`

Default `86400` (24h). Set on Redis at acquire-time via INCR's `expire: true, ttl: <n>` parameter. **Server-enforced** — a crashed holder's lock auto-expires after `ttl_seconds`. Tune per workflow:

- A payment workflow with a 5-minute critical section → `--ttl-seconds 600` (10 min, generous buffer).
- A long batch job that may run for 6 hours → `--ttl-seconds 32400` (9h, also generous).

The TTL is NOT a wait timeout; it bounds how long an orphaned lock blocks the scope after a crash.

### `--max-wait-seconds <int>`

Default `86400` (24h) — effectively unbounded for typical use. The waiter polls every 1 second until either it acquires or `max_wait_seconds` elapses. Override per-workflow if you need fail-fast-ish semantics for time-sensitive callers:

- Webhook handler: `--max-wait-seconds 30` (give up after 30s, let upstream retry/queue).
- User-facing API: `--max-wait-seconds 5` (don't block users for long).
- Background batch: leave at default (background work can wait).

`max_wait_seconds` is the wait-loop's deadline, distinct from `ttl_seconds` (which bounds crashed-holder leak time).

### `--fail-fast`

Default off. When set, passes `wait_till_lock_released: false` to the acquire primitive: if the lock is held, the workflow Stop-and-Errors immediately with a message including the current count. Without this flag, the primitive enters the wait loop.

`--fail-fast` and `--max-wait-seconds 0` are NOT equivalent. `--max-wait-seconds 0` would make the deadline immediate (after the first failed INCR + Wait + GET, the timeout fires). `--fail-fast` skips the wait loop entirely and errors directly after the first failed INCR.

### `--lock-on-error`

Default off. When set, also sets your workflow's `settings.errorWorkflow` to `error_handler_lock_cleanup`. The cleanup primitive is currently a no-op stub (orphan locks rely on Redis-side TTL); the flag is wired so an upgrade to active cleanup later doesn't require re-running this helper.

## Worked example

```bash
# 1. Make sure the lock pair is in your workspace.
python3 ${CLAUDE_PLUGIN_ROOT}/helpers/create_lock.py

# 2. Wrap your workflow with a 10-minute TTL, scoping per Excel file.
python3 ${CLAUDE_PLUGIN_ROOT}/helpers/add_lock_to_workflow.py \
  --workflow-key sharepoint_writeback \
  --scope-expression "='excel-' + $json.fileId" \
  --ttl-seconds 600 \
  --max-wait-seconds 60
```

The result on the wire:

```
Webhook → Lock Acquire (scope=excel-<fileId>, ttl=600, max_wait=60)
       → ... your writeback nodes ...
       → Lock Release (scope=excel-<fileId>)
```

Two simultaneous webhooks for the same `fileId` race at Lock Acquire. The first wins (INCR returns 1); the second sees `count === 2`, branches to Should Wait → Wait Before Poll → GET → loops until either the first releases (next INCR succeeds) or 60 seconds elapse (Wait Timeout — Stop fires). Two webhooks for *different* `fileId`s acquire independent locks — no contention.

## Webhook example with shorter wait

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/helpers/add_lock_to_workflow.py \
  --workflow-key user_facing_api \
  --scope-expression "='user-' + $json.userId" \
  --ttl-seconds 60 \
  --max-wait-seconds 5
```

The `max_wait_seconds 5` means a contended call gives up after 5 seconds — short enough that the user doesn't notice but long enough to absorb sub-second contention bursts.

## Pattern + caveats

See [`skills/patterns/locking.md`](patterns/locking.md) for:
- The atomic-INCR safety model (race-on-acquire is prevented by Redis serialization).
- TTL vs max-wait-seconds distinction.
- "When NOT to use" (multi-region Redis, fairness-required, sub-millisecond contention).
- Position-shift heuristic ([position-recalculation](patterns/position-recalculation.md)).
