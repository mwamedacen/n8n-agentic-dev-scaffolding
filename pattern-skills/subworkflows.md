# Sub-workflows: Execute Workflow + tier ordering

## When to use

When a workflow needs to call another workflow as a subroutine — the canonical n8n pattern is the `Execute Workflow` node (`n8n-nodes-base.executeWorkflow`). The callee receives the parent's data and returns a result; the parent continues from there.

## Mechanics

1. Author the **callee** as its own template, with an Execute Workflow trigger node (`n8n-nodes-base.executeWorkflowTrigger`) as the entry point. The callee returns whatever the last node emits.
2. In the **caller**, use Execute Workflow node and reference the callee by ID:

   ```json
   {
     "parameters": {
       "workflowId": "={{HYDRATE:env:workflows.<callee_key>.id}}"
     },
     "type": "n8n-nodes-base.executeWorkflow"
   }
   ```

   Note the `=` prefix — that's n8n's expression syntax. Without it, the workflow uses a literal `{{HYDRATE:env:...}}` string.

3. Place the **callee in an earlier tier** in `n8n/deployment_order.yaml` so its ID is assigned by `bootstrap()` before the caller is deployed:

   ```yaml
   tiers:
     - name: "Tier 1: Subworkflows"
       workflows:
         - data_extraction
     - name: "Tier 2: Pipelines that call them"
       workflows:
         - main_pipeline
   ```

## Worked example: existing `lock_acquisition` / `lock_release`

`n8n/environments/dev.yaml` has these sub-workflows. They're called by pipelines that need critical-section semantics. Each is a full `*.template.json`; the pipelines reference them via:

```json
"workflowId": "={{HYDRATE:env:workflows.lock_acquisition.id}}"
```

Tier 1 contains all three lock-related workflows; pipelines that use them sit in tier 2+.

## Common traps

- **Forgetting the `=` prefix.** If the parameter value is exactly `{{HYDRATE:env:...}}` without `=`, n8n treats it as a literal string and tries to find a workflow with that name — fails at runtime.
- **Wrong tier order.** If the callee's ID is still placeholder when the caller is deployed, n8n returns 404. Always run `bootstrap(env)` before `deploy()` for new workflows, or run the bash `./deploy_all.sh <env>` which respects tier order.
- **Resync loses the placeholder.** After resync, the `workflowId` is replaced with the literal callee ID (a UUID-like string). The dehydrate step replaces it back with `{{HYDRATE:env:workflows.<key>.id}}` — but only if the `<key>` was already in YAML at resync time. Adding workflows to YAML before resync is the safe order.
