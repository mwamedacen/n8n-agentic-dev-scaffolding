# n8n Deployment Scripts

## Quick Start

```bash
# Deploy everything to dev (auto-deactivates after)
./deploy_all.sh dev

# Deploy everything to dev and keep workflows active
./deploy_all.sh dev --keep-active

# Deploy a single workflow
./deploy_workflow.sh dev periodic_excel_report

# Deploy to production
./deploy_all.sh prod

# Bootstrap placeholder workflows for a new environment
python3 bootstrap_workflows.py dev

# Deactivate all workflows
./deactivate_all.sh dev
```

## deploy_workflow.sh

Deploys a single workflow to an n8n environment. Handles hydration, upload, and activation in one step.

```bash
./deploy_workflow.sh <env> <workflow_key>
```

**What it does:**
1. Loads the environment config and secrets
2. Auto-discovers the template at `n8n/workflows/{workflow_key}.template.json`
3. Runs hydration via `hydrate_workflow.py`
4. Uploads the generated JSON to n8n via `PUT /api/v1/workflows/{id}`
5. Activates the workflow via `POST /api/v1/workflows/{id}/activate`

## deploy_all.sh

Deploys all workflows in tier order as defined in `deployment_order.yaml`.

```bash
./deploy_all.sh <env> [--keep-active|-k]
```

**Behavior:**
- Reads tiers from `n8n/deployment_order.yaml`
- Deploys each workflow in tier order (tier 1 first, then tier 2, etc.)
- For `dev` environment: automatically deactivates all workflows after deployment (safety measure)
- Use `--keep-active` or `-k` to skip dev auto-deactivation
- Non-dev environments always keep workflows active

## deployment_order.yaml

Defines the deployment order using tiers. Workflows within the same tier have no mutual dependencies.

```yaml
tiers:
  - name: "Tier 1: Leaf Subworkflows"
    workflows:
      - lock_acquiring
      - data_extraction

  - name: "Tier 2: Mid-level Workflows"
    workflows:
      - store_attachments

  - name: "Tier 3: Top-level Orchestrators"
    workflows:
      - main_pipeline
```

**Why tiers matter:** If workflow A calls subworkflow B via "Execute Workflow" node, B must be deployed first so its ID is available. Place B in an earlier tier than A.

## Dev Auto-Deactivation

When deploying to `dev`, `deploy_all.sh` automatically deactivates all workflows after deployment. This prevents dev workflows from running on schedules or webhooks while you are still setting up.

To keep workflows active in dev:
```bash
./deploy_all.sh dev --keep-active
```

## bootstrap_workflows.py

Creates empty placeholder workflows in n8n via the API and records the assigned IDs in the environment YAML config.

```bash
python3 bootstrap_workflows.py dev
python3 bootstrap_workflows.py prod --dry-run
```

**What it does:**
1. Reads all workflow entries from the environment YAML
2. Skips workflows that already have an ID
3. Creates a minimal empty workflow in n8n for each entry
4. Updates the YAML config with the new workflow IDs

**When to use:**
- Setting up a new environment for the first time
- Adding a new workflow to the project
- After adding workflow entries to the YAML with placeholder IDs

## deactivate_all.sh

Deactivates all workflows for an environment by reading workflow IDs from the YAML config.

```bash
./deactivate_all.sh <env>
```

## YAML Config Structure

Each environment config in `n8n/environments/{env}.yaml`:

```yaml
name: dev
displayName: "Development"
workflowNamePostfix: " [DEV]"

n8n:
  instanceName: "your-instance.app.n8n.cloud"

credentials:
  msOauth:
    id: "credential-id"
    name: "dev_ms_oauth"

workflows:
  periodic_excel_report:
    id: "12345"          # Assigned by n8n during bootstrap
    name: "Periodic Excel Report"
```

## .env Secrets Format

Secrets are stored in `.env.{env}` files (gitignored):

```
N8N_API_KEY=your_api_key_here
```

The `_common.sh` helper loads these via `source .env.{env}` and checks that `N8N_API_KEY` is set.

## Troubleshooting

### "N8N_API_KEY is not set"
Create or check your `.env.{env}` file. Example: `.env.dev` should contain `N8N_API_KEY=...`.

### "Environment config not found"
Ensure `n8n/environments/{env}.yaml` exists. Run `ls n8n/environments/` to see available configs.

### "Template file not found"
Templates must follow the naming convention `n8n/workflows/{workflow_key}.template.json`. The key must match what you pass to the deploy script.

### "Workflow key not found or has no id"
The workflow key must exist in the environment YAML under `workflows:` with a valid `id`. Run `bootstrap_workflows.py` if you need to create placeholder workflows.

### "Upload failed (HTTP 404)"
The workflow ID in the YAML may be incorrect. Re-run `bootstrap_workflows.py` or manually check the workflow ID in the n8n UI.

### "Upload failed (HTTP 401)"
Your `N8N_API_KEY` is invalid or expired. Generate a new one in n8n under Settings > API.
