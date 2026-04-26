---
name: resync-single-workflow-from-env
description: Pull live state of one workflow back into its template.
---

# resync-single-workflow-from-env

## When

After someone edits a workflow in the n8n UI and you want the template to reflect those changes.

## How

```bash
python3 <harness>/helpers/resync.py --env <env> --workflow-key <key>
```

## Side effects

- `GET /api/v1/workflows/<id>` from env's n8n.
- Runs the dehydrate pipeline:
  - Strips volatile metadata (id, active, versionId, createdAt, updatedAt, tags, pinData).
  - Restores UUID placeholders by node-name lookup against the existing template.
  - Reverse-substitutes env values back into `{{HYDRATE:env:...}}` placeholders.
  - Restores JS code blocks via DEHYDRATE markers.
- Writes `<workspace>/n8n-workflows-template/<key>.template.json`.
