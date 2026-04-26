---
name: deactivate-single-workflow-in-env
description: Pause a workflow's triggers (commonly during dev).
---

# deactivate-single-workflow-in-env

## When

You want to pause a workflow's triggers without removing the workflow.

## How

```bash
python3 <harness>/helpers/deactivate.py --env <env> --workflow-key <key>
```

POST `/api/v1/workflows/<id>/deactivate`. Idempotent on the n8n side.
