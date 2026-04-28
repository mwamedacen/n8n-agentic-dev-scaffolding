---
description: Apply n8n's canvas-layout algorithm to a workflow template so node positions are clean and consistent.
---

# tidyup

Apply the canvas-layout algorithm to a workflow template. Runs the `@n8n/workflow-sdk` dagre layouter (auto-installed on first use); falls back to pure-Python BFS if Node is unavailable. Sticky notes are never moved.

## How

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/helpers/tidy_workflow.py --workspace <ws> --workflow-key <key> --in-place
```

See full options, side effects, idempotence, and auto-tidy hook details in [`skills/tidy-workflow.md`](tidy-workflow.md).
