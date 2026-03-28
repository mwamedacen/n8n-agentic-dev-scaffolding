---
description: Resync n8n workflows from a live instance back to local templates. Usage: /resync dev, /resync prod po_reconciliation_pipeline
---

Resync n8n workflows from the specified environment back to local template files.

Parse "$ARGUMENTS" to extract:
- First word: environment name (e.g., "dev", "prod")
- Second word (optional): specific workflow key (e.g., "po_reconciliation_pipeline")

If a specific workflow key is provided, resync just that workflow:
```bash
n8n/resync_scripts/resync_workflow.sh <env> <workflow_key>
```

If no workflow key is provided, resync all workflows:
```bash
n8n/resync_scripts/resync_all.sh <env>
```

After resync, run `git diff n8n/workflows/` and show the user what changed so they can review before committing.
