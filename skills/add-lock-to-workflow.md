---
name: add-lock-to-workflow
description: Insert lock acquire / release Execute Workflow nodes around a workflow's main flow.
---

# add-lock-to-workflow

## When

An existing workflow needs to wrap its critical section in distributed-lock acquire / release calls.

## How

```bash
python3 <harness>/helpers/add_lock_to_workflow.py \
  --workflow-key <wf> \
  [--lock-on-error] \
  [--scope-expression "lock-{{ $execution.id }}"] \
  [--max-wait-ms 0] \
  [--poll-interval-ms 200] \
  [--ttl-seconds 60]
```

## Side effects

- Edits `<workspace>/n8n-workflows-template/<wf>.template.json`:
  - Inserts an `Execute Workflow` node calling `lock_acquisition` right after the trigger.
  - Inserts an `Execute Workflow` node calling `lock_release` after the terminal node(s).
  - Recalculates downstream node positions (220 px right shift).
- With `--lock-on-error`, also sets `settings.errorWorkflow` to `error_handler_lock_cleanup` (delegates to `register-workflow-to-error-handler`).

Refuses if lock primitives aren't yet in the workspace — run `create-lock.md` first.

## Wait mode (`--max-wait-ms`)

Default behavior is **fail-fast**: if the lock is already held, `lock_acquisition` returns `{ acquired: false }` immediately and your workflow can branch on it. Set `--max-wait-ms <N>` to switch to **wait-with-timeout**: the primitive polls every `--poll-interval-ms` (default 200 ms) until either it acquires or the deadline passes.

```bash
# wait up to 2 seconds, polling every 100 ms
python3 <harness>/helpers/add_lock_to_workflow.py \
  --workflow-key my_workflow \
  --max-wait-ms 2000 \
  --poll-interval-ms 100
```

The acquire node's output payload is `{ acquired, scope, waitedMs }` in both modes.

### Worker-pinning caveat

Wait mode holds the n8n worker for the entire `maxWaitMs` window. Saturating your worker pool with too many concurrent waiters can deadlock unrelated traffic. Recommendation:

- Keep `--max-wait-ms ≤ 2000` unless you have measured your worker-pool depth and know it can absorb the held workers.
- Above 2000 ms, prefer architectural fixes (queue, retry-on-fail, smaller scopes) over a longer wait.
- Pub-sub-based wait (no polling, no held worker) is intentionally out of scope — bounded polling is the trade-off.

## TTL (`--ttl-seconds`)

Default 60 s. The lock's Redis key auto-expires after this if the workflow crashes between `lock_acquisition` and `lock_release` (and the error-handler cleanup never runs). Tune for your longest reasonable critical-section runtime.

The owner pointer (`lock-owner-<executionId>`) shares the lock TTL — both keys expire together.

## Default-omission discipline

Default values for `--max-wait-ms` (0), `--poll-interval-ms` (200), and `--ttl-seconds` (60) are **omitted** from the acquire node's `workflowInputs.value`. The primitive's own defaults apply, which means:

- Existing workflows that ran `add-lock-to-workflow` without these flags before they existed are byte-identical after upgrade.
- The wait flags only show up in the template when you actually opt in.

## Pattern

See `skills/patterns/locking.md` for the full picture of fail-fast / wait / rate-limit modes and `skills/patterns/position-recalculation.md` for the position-shift heuristic.
