# n8n Workflows Directory

## Template vs Generated Files

- **Templates** (`*.template.json`): Version-controlled source of truth. Contain placeholders that get resolved during hydration. These are what you edit.
- **Generated** (`generated/{env}/*.generated.json`): Environment-specific hydrated output. Created by the build scripts, gitignored, and uploaded to n8n via the deployment scripts.

Never edit generated files directly -- changes will be overwritten on next hydration.

## Placeholder Syntax Reference

Templates use six placeholder types, all following the pattern `{{HYDRATE:type:value}}`:

### 1. Environment Values (`env`)
```
{{HYDRATE:env:sharepoint.driveId}}
{{HYDRATE:env:credentials.msOauth.id}}
{{HYDRATE:env:cloudFunction.apiUrl}}
{{HYDRATE:env:workflows.periodic_excel_report.id}}
```
Resolves to the value at that dot-notation path in the environment YAML config.

### 2. Text Files (`txt`)
```
{{HYDRATE:txt:common/prompts/data_summary_prompt.txt}}
```
Inlines the file contents as an escaped string. Used for AI prompts.

### 3. JSON Files (`json`)
```
{{HYDRATE:json:common/prompts/data_summary_schema.json}}
```
Inlines the JSON file contents as a stringified JSON value. Used for response schemas.

### 4. HTML/Template Files (`html`)
```
{{HYDRATE:html:common/templates/report_email.template.txt}}
```
Inlines HTML or text template contents. Used for email bodies.

### 5. JavaScript Files (`js`)
```
{{HYDRATE:js:common/functions/process_excel_data.js}}
```
Inlines JavaScript file contents for n8n Code nodes. Files can include `// DEHYDRATE:START` and `// DEHYDRATE:END` markers to enable round-trip resync.

### 6. UUIDs (`uuid`)
```
{{HYDRATE:uuid:schedule-trigger-id}}
{{HYDRATE:uuid:schedule-trigger-webhookId}}
```
Generates a fresh UUID v4 on each hydration. Used for trigger node IDs and webhook IDs.

**Why this matters for multi-environment:** n8n uses trigger node IDs (especially `webhookId`) to register webhook and schedule listeners. If two environments (dev and prod) on the same n8n instance share identical trigger IDs, they collide -- one webhook overwrites the other, causing only one environment's workflow to fire. By generating fresh UUIDs per environment during hydration, each environment gets unique trigger registrations that don't interfere with each other. During dehydration (resync), these UUIDs are replaced back with `{{HYDRATE:uuid:...}}` placeholders to keep templates portable.

## Naming Convention

Templates follow the pattern:

```
{workflow_key}.template.json
```

Where `workflow_key` matches the key used in `n8n/environments/*.yaml` under `workflows:`. Examples:

- `periodic_excel_report.template.json` matches `workflows.periodic_excel_report`
- `invoice_processor.template.json` matches `workflows.invoice_processor`

## Generated File Location

```
generated/{env}/{workflow_key}.generated.json
```

For example:
- `generated/dev/periodic_excel_report.generated.json`
- `generated/prod/periodic_excel_report.generated.json`

## How Connections Work in n8n JSON

The `connections` object maps source node **names** (not IDs) to their outputs:

```json
{
  "connections": {
    "Schedule Trigger": {
      "main": [
        [
          {
            "node": "Read Excel from SharePoint",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  }
}
```

Key rules:
- Keys are **node names** (the `name` field), not node IDs
- `main` is the standard output type (AI nodes may use `ai_agent`, `ai_tool`, etc.)
- The outer array represents output indices (most nodes have one output at index 0)
- The inner array lists all nodes connected to that output

## pinData Policy

**Never include `pinData` in template files.** Pin data is test/debug data that should only exist in the n8n UI during development. It inflates template size and can cause unexpected behavior during deployment.

If a resync pulls in pinData, remove it before committing.

## Node Positioning

Position nodes on a grid for readability:
- Horizontal spacing: approximately 220px between sequential nodes
- Vertical spacing: approximately 200px between parallel branches
- Start position: `[0, 0]` for the trigger node
- Flow left to right

### Recalculate positions after changes

**When you add, remove, or reorder nodes, you MUST recalculate all downstream positions.** This is the most common source of overlapping or unreadable workflow layouts in the n8n UI.

Rules:
1. **Adding a node mid-flow**: Shift all subsequent nodes right by 220px
2. **Removing a node**: Shift all subsequent nodes left by 220px to close the gap
3. **Adding a branch (If/Switch)**: Place the true branch at current Y, false branch at Y+200. Merge node goes at the max X of both branches + 220px
4. **Inserting before a branch**: Shift the entire branch subtree (both paths) right

Example — inserting "Validate" between nodes at positions [440, 0] and [660, 0]:
- "Validate" gets [660, 0]
- The old [660, 0] node moves to [880, 0]
- All nodes after it shift right by 220px

n8n will render whatever positions you set — it does NOT auto-layout. Incorrect positions cause nodes to stack on top of each other, making the workflow unreadable in the UI.

## Advanced: Variant Workflows

For complex AI workflows, you may need variant patterns:

### Chat + Subworkflow Pattern

A parent chat workflow triggers a subworkflow for processing:

```
chat_interface.template.json          (Tier 2 - depends on subworkflow)
chat_processing_sub.template.json     (Tier 1 - leaf subworkflow)
```

The parent references the subworkflow by ID using:
```json
"workflowId": "={{HYDRATE:env:workflows.chat_processing_sub.id}}"
```

This pattern is not in the sample template but is supported by the hydration system. Place subworkflows in earlier tiers in `deployment_order.yaml` so their IDs are available when the parent is deployed.
