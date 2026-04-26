---
name: add-lock-to-workflow
description: Insert lock acquire / release Execute Workflow nodes around a workflow's main flow.
---

# add-lock-to-workflow

## When

An existing workflow needs to wrap its critical section in distributed-lock acquire / release calls.

## How

```bash
python3 <harness>/helpers/add_lock_to_workflow.py --workflow-key <wf> [--lock-on-error] [--scope-expression "lock-{{ $execution.id }}"]
```

## Side effects

- Edits `<workspace>/n8n-workflows-template/<wf>.template.json`:
  - Inserts an `Execute Workflow` node calling `lock_acquisition` right after the trigger.
  - Inserts an `Execute Workflow` node calling `lock_release` after the terminal node(s).
  - Recalculates downstream node positions (220 px right shift).
- With `--lock-on-error`, also sets `settings.errorWorkflow` to `error_handler_lock_cleanup` (delegates to `register-workflow-to-error-handler`).

Refuses if lock primitives aren't yet in the workspace — run `create-lock.md` first.

## Pattern

See `skills/patterns/locking.md` and `skills/patterns/position-recalculation.md`.
