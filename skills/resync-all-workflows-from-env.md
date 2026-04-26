---
name: resync-all-workflows-from-env
description: Snapshot a full env back to templates.
---

# resync-all-workflows-from-env

## When

A periodic backup of all live workflows, or after a UI editing session that touched many workflows.

## How

```bash
python3 <harness>/helpers/resync_all.py --env <env>
```

Iterates every key in `<env>.yml.workflows`, calls `resync.py` per key. Returns non-zero exit if any resync failed.
