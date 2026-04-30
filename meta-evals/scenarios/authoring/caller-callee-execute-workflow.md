---
id: caller-callee-execute-workflow
category: authoring
difficulty: medium
---

# Caller workflow that invokes a sub-workflow via Execute Workflow

## Prompt

> "Build two workflows: `pricing_calc` (input: SKU; output: price) called as a sub-workflow by `order_processing`. Order processing takes an order, calls pricing_calc per item, and tallies a total."

## Expected skills consulted

1. `skills/create-new-workflow.md`
2. `skills/patterns/subworkflows.md`
3. `skills/deploy_all.md` (for tier-ordered deploy of callee → caller)

## Expected helpers invoked

1. `helpers/create_workflow.py --key pricing_calc --name "Pricing Calc" --register-in dev --tier "Tier 0a: leaves"`
2. `helpers/create_workflow.py --key order_processing --name "Order Processing" --register-in dev --tier "Tier 1"`
3. (template authoring with Execute Workflow node in caller, executeWorkflowTrigger in callee)
4. `helpers/validate.py --workflow-key pricing_calc`
5. `helpers/validate.py --workflow-key order_processing`
6. `helpers/deploy_all.py --env dev`

## Expected artifacts

- `n8n-workflows-template/pricing_calc.template.json` with `executeWorkflowTrigger` head + Set or Code body returning `{price: <n>}`.
- `n8n-workflows-template/order_processing.template.json` with Webhook head and an `executeWorkflow` node referencing `{{@:env:workflows.pricing_calc.id}}` via `mode: id` `__rl: true` shape.
- `n8n-config/deployment_order.yml` updated so `pricing_calc` is in Tier 0a and `order_processing` in Tier 1.

## Expected state changes

- Both workflows deployed and activated. Tier order ensures callee activates first.

## Success criteria

- [ ] `curl` on the order_processing webhook returns the tally.
- [ ] `dependency_graph.py --env dev` shows `order_processing → pricing_calc` edge.
- [ ] Both executions visible via `list_executions.py`.

## Pitfalls

- **n8n Cloud sub-workflow caveat**: callee must be active (n8n's "publish" state) before caller can be activated. n8n's public REST API has NO `/publish` endpoint — `POST /workflows/{id}/activate` IS the publish action. The caveat is documented in `skills/deploy.md`. `deploy_all.py` with proper tier ordering handles this automatically; deploying the caller first directly will 400 on activate.
- Inside the caller, the executeWorkflow node's `parameters.workflowId` should be in `__rl: true, value: "{{@:env:workflows.pricing_calc.id}}", mode: "id"` shape. typeVersion 1.2 in `defineBelow` mode for `workflowInputs.value` requires expressions in canonical `={{ ... }}` form.
- If the agent passes the caller-callee mapping incorrectly and dependency_graph shows no edge, double-check the executeWorkflow node's `workflowId` field — the parser keys on placeholder name, not literal id.
