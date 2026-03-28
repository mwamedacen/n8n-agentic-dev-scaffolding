---
description: Scaffold a new n8n workflow template with all required config entries
---

Create a new n8n workflow template with the name "$ARGUMENTS".

Steps:
1. Create the template file at `n8n/workflows/$ARGUMENTS.template.json` with a basic structure including:
   - A Schedule Trigger node with `{{HYDRATE:uuid:schedule-trigger-id}}` and `{{HYDRATE:uuid:schedule-trigger-webhookId}}` placeholders
   - A Set node with `{{HYDRATE:env:displayName}}` placeholder showing the environment name
   - Proper connections between nodes
   - `"meta": {"templateCredsSetupCompleted": true}`

2. Add the workflow to `n8n/environments/dev.yaml` under `workflows:`:
   ```yaml
   $ARGUMENTS:
     id: "TODO"
     name: "TODO - Set Workflow Name"
   ```

3. Add the workflow to `n8n/environments/prod.yaml` with the same structure.

4. Add the workflow to `n8n/deployment_order.yaml` in the appropriate tier. If unsure, add to the last tier as independent.

5. Show the user what was created and suggest next steps:
   - Edit the template to add nodes and placeholders
   - Run `python3 n8n/deployment_scripts/bootstrap_workflows.py dev` to create the workflow in n8n and get the real ID
   - Run `n8n/deployment_scripts/deploy_workflow.sh dev $ARGUMENTS` to deploy
