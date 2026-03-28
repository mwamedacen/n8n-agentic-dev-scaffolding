# n8n Resync Scripts

## Quick Start

```bash
# Resync a single workflow from dev
./resync_workflow.sh dev periodic_excel_report

# Resync all workflows from dev
./resync_all.sh dev

# Resync from prod
./resync_all.sh prod

# Resync and remove trigger nodes
./resync_workflow.sh dev periodic_excel_report true
```

## resync_workflow.sh

Fetches a single workflow from the n8n API, dehydrates it, and saves the result as a template file.

```bash
./resync_workflow.sh <env> <workflow_key> [remove_triggers]
```

Arguments:
- `env`: Environment name (dev, prod, etc.)
- `workflow_key`: Workflow key matching the YAML config
- `remove_triggers` (optional): Pass `true` to strip trigger nodes during dehydration

**What it does:**
1. Loads the environment config and secrets
2. Looks up the workflow ID from the YAML
3. Fetches the live workflow JSON from `GET /api/v1/workflows/{id}`
4. Runs dehydration to restore placeholder syntax
5. Saves the result to `n8n/workflows/{workflow_key}.template.json`

## resync_all.sh

Auto-discovers all workflow keys from the environment YAML and resyncs each one.

```bash
./resync_all.sh <env>
```

Iterates through all entries under `workflows:` in the YAML config and calls `resync_workflow.sh` for each.

## Dehydration Process

Dehydration is the reverse of hydration. It takes a live workflow JSON from n8n and converts it back into a template with placeholders.

The dehydration process:

1. **Fetch** the live workflow JSON from the n8n API
2. **Remove metadata** that is runtime-specific and should not be version-controlled:
   - `id` (top-level workflow ID)
   - `versionId`
   - `createdAt`, `updatedAt` timestamps
   - `active` status
   - `staticData`
   - `pinData`
   - `tags` (often instance-specific)
3. **Restore placeholders** where hydrated values match known patterns:
   - Config values get replaced with `{{HYDRATE:env:...}}` placeholders
   - File contents get replaced with `{{HYDRATE:txt/json/html:...}}` placeholders
   - JavaScript blocks between DEHYDRATE markers get replaced with `{{HYDRATE:js:...}}`
   - Trigger node IDs get replaced with `{{HYDRATE:uuid:...}}` placeholders
4. **Preserve** the core workflow structure:
   - All nodes and their parameters
   - All connections between nodes
   - Workflow settings
   - Node positions

## What Gets Removed

| Field | Reason |
|-------|--------|
| `id` | Instance-specific, different per environment |
| `versionId` | Changes on every save in the n8n UI |
| `updatedAt` / `createdAt` | Timestamps that cause unnecessary diffs |
| `active` | Controlled by deployment scripts, not templates |
| `staticData` | Runtime execution state |
| `pinData` | Debug/test data, should not be in templates |
| `tags` | Often instance-specific |

## What Gets Preserved

| Field | Reason |
|-------|--------|
| `name` | Workflow display name (postfix gets stripped) |
| `nodes` | The actual workflow logic |
| `connections` | How nodes are wired together |
| `settings` | Execution order, timezone, etc. |
| `meta` | Template metadata |

## When to Use Resync

- **After UI changes**: You edited a workflow directly in the n8n UI and want to capture those changes in version control
- **Team sync**: A teammate made changes in the n8n UI that you need in your repo
- **Backups**: Periodically resync to ensure your templates reflect the live state
- **Initial import**: Converting an existing n8n workflow into a managed template for the first time

## After Resync

1. Review changes: `git diff n8n/workflows/`
2. Test by re-hydrating: `cd ../build_scripts && python3 hydrate_all.py -e dev`
3. Commit if satisfied
