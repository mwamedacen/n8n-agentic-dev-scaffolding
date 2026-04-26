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
Generates a fresh UUID v4 on each hydration. Used for trigger-node `id` and `webhookId` fields.

> **Why per-env UUIDs matter** — see `pattern-skills/multi-env-uuid-collision.md`. (Content migrated out of this AGENTS.md per Phase 2 step 5.)

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

When you add, remove, or reorder nodes, recalculate all downstream positions — n8n does NOT auto-layout. Full rules and worked examples live in `pattern-skills/multi-env-uuid-collision.md` (positioning section). (Content migrated out of this AGENTS.md per Phase 2 step 5.)

## Sub-workflows

Parent workflows reference callees via `"workflowId": "={{HYDRATE:env:workflows.<callee_key>.id}}"` (note the `=` prefix for n8n expression mode). Place callees in earlier tiers in `deployment_order.yaml`. Full pattern + worked examples: `pattern-skills/subworkflows.md`.

## Demo suite — runnable vs structural-only

The `demo_*` templates split into two classes (canonical lists in `helpers.RUNNABLE_DEMOS` / `helpers.STRUCTURAL_ONLY_DEMOS`):

**Runnable** (programmatically firable → must reach a known terminal status):

| Demo | Trigger | Expected status | Notes |
|---|---|---|---|
| `demo_smoke` | Webhook | `success` | Set node |
| `demo_branching` | Webhook | `success` | Switch + If + Merge + Code |
| `demo_batch_processor` | Webhook | `success` | SplitInBatches + Code |
| `demo_subworkflow_caller` | Webhook | `success` | Execute Workflow → demo_subworkflow_callee |
| `demo_external_js_code` | Webhook | `success` | Code with `{{HYDRATE:js:...}}` |
| `demo_http_call` | Webhook | `success` | HTTP Request to public endpoint |
| `demo_ai_summary` | Webhook | `success` | Code that inlines `{{HYDRATE:txt:...}}` prompt + `{{HYDRATE:json:...}}` schema (mocks the LLM call; see template comment) |
| `demo_scheduled_report` | Schedule + Webhook | `success` | Dual trigger; Schedule for coverage, Webhook for runnability |
| `demo_chat_assistant` | Chat + Webhook | `success` | Dual trigger; Chat for coverage, Webhook for runnability |
| `demo_error_source` | Webhook | **`error`** | Intentional failure — see "source/handler pair pattern" below |
| `demo_error_handler` | Error Trigger | `success` | Fired indirectly: `run_workflow("demo_error_handler")` fires `demo_error_source`, n8n routes the error → handler executes |

**Structural-only** (cannot be programmatically invoked → verified via deploy + `GET /workflows/{id}` round-trip identity, NOT runtime status):

| Demo | Trigger class | Why structural-only |
|---|---|---|
| `demo_subworkflow_callee` | Execute Workflow Trigger callee | Fires only when invoked from a parent workflow |
| `demo_locked_pipeline` | Manual + Execute Workflow → lock_acquiring/releasing | References sub-workflows that need real Redis credentials; placeholder IDs in YAML |
| `demo_integrations_showcase` | Manual + Microsoft 365 + Gmail + Redis | Needs real credentials (placeholder IDs in YAML) |

Plan-level §5 carve-out: every runnable demo reaches its expected terminal status; structural-only demos verify deploy + GET round-trip only. See plan §6 for the rationale.

### Source/handler pair pattern (with lock-on-error)

n8n's Error Trigger workflows can't be fired directly via REST — they fire only when another workflow whose `settings.errorWorkflow` points at them fails. The harness exercises this with **paired demos**:

- **`demo_X_source`** — Webhook-triggered, *intentionally fails* (e.g., a Code node that throws).
  Has `settings.errorWorkflow = "{{HYDRATE:env:workflows.demo_X_handler.id}}"` so n8n knows where to route the error context. `wait_for_execution(..., expect_status="error")` confirms the failure happened.
- **`demo_X_handler`** — Error Trigger workflow. Fires automatically when n8n catches the source's failure. Reads error context (workflow name, error message, error node, source execution id), runs cleanup, and exits with `status="success"`.

The current pair (`demo_error_source` + `demo_error_handler`) demonstrates n8n's canonical **lock-leak-on-error** handling — the most common reason to wire up an Error Trigger workflow:

1. **`demo_error_source`** (Webhook → Set "Derive Lock Key" → Execute Workflow `lock_acquiring` → Redis "Store Lock Meta" → Code "Throw"):
   - Derives a deterministic lock key from `$execution.id`: `demo-error-source-lock-<exec_id>`.
   - Acquires the lock via `lock_acquiring` sub-workflow (returns `{lock_id, scope}`).
   - Stores the `lock_id` in Redis under a meta key `demo-error-source-lockmeta-<exec_id>` (TTL 60s) so the handler can recover it.
   - Throws. Lock would normally leak forever without the handler.
2. **`demo_error_handler`** (Error Trigger → Set "Derive Lock Key" → Redis "Recover Lock ID" → Execute Workflow `lock_releasing` → Set "Capture Error"):
   - Derives the same lock key + meta key from `$json.execution.id` (the failed source's exec id).
   - GETs the meta key from Redis to recover the original `lock_id`.
   - Releases the lock via `lock_releasing` (which validates ownership before deleting — the recovered `lock_id` matches the stored one, so DEL fires).
   - Final Set node emits `{handled: true, lock_released: true, source_workflow_name, source_workflow_id, error_message, error_node, source_execution_id, released_lock_scope, handled_at}`.

End-to-end chain (4 executions, all visible in n8n UI):
```
demo_error_source(error)
  → lock_acquiring(success)
  → demo_error_handler(success)
      → lock_releasing(success)
```

Tier order in `deployment_order.yaml`: handlers + lock primitives come first (they're callees), then sources (which reference handler IDs in `settings.errorWorkflow`).

Any future Error Trigger demo should follow the same naming + wiring convention so `helpers._INDIRECT_VIA_ERROR_SOURCE` can dispatch.
