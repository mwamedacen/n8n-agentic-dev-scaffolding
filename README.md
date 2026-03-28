# n8n Agentic Dev Scaffolding

A production-grade scaffolding for developing, deploying, and managing n8n workflows as code with multi-environment support, template hydration/dehydration, cloud functions, and AI prompt engineering.

## Features

- **Hydration/Dehydration** -- Write workflow templates with placeholders; hydrate them into environment-specific deployable JSON, and dehydrate live workflows back into templates.
- **Multi-Environment Support** -- Separate YAML configs and `.env` secrets for dev, staging, prod, or any custom environment.
- **One-Command Deploy** -- Deploy a single workflow or all workflows in tier-based order with automatic hydration.
- **Resync from n8n** -- Pull live workflow changes from the n8n UI back into version-controlled templates.
- **Cloud Functions** -- A FastAPI service (Railway-ready) for exposing pure Python functions as HTTP endpoints callable from n8n.
- **DSPy Prompt Engineering** -- Evaluate and optimize prompts used in n8n AI nodes using DSPy signatures and modules.

## Quick Start

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd n8n-scaffolder-for-coding-agents

# 2. Run the interactive setup wizard
bash setup.sh

# 3. Or set up manually:
pip3 install pyyaml
cp .env.dev.example .env.dev    # Edit with your API key
# Edit n8n/environments/dev.yaml with your instance URL and credentials

# 4. Bootstrap placeholder workflows in n8n
python3 n8n/deployment_scripts/bootstrap_workflows.py dev

# 5. Hydrate and deploy
cd n8n/build_scripts && python3 hydrate_all.py -e dev
cd n8n/deployment_scripts && ./deploy_all.sh dev
```

## Architecture Overview

### How Hydration Works

Workflow templates (`n8n/workflows/*.template.json`) contain **placeholders** that get resolved during hydration into environment-specific generated files.

```
Template (version controlled)     Environment Config (YAML)
          |                                |
          v                                v
    +-----------+                  +----------------+
    | hydrate_  |  <-- reads -->   | dev.yaml       |
    | workflow  |                  | prod.yaml      |
    | .py       |                  +----------------+
    +-----------+
          |
          v
  Generated JSON (gitignored)
  n8n/workflows/generated/dev/workflow.generated.json
```

### Placeholder Types

| Type | Syntax | Resolves To | Example |
|------|--------|-------------|---------|
| `env` | `{{HYDRATE:env:key.path}}` | Value from YAML config (dot notation) | `{{HYDRATE:env:sharepoint.driveId}}` |
| `txt` | `{{HYDRATE:txt:path/to/file.txt}}` | File contents as escaped string | `{{HYDRATE:txt:common/prompts/data_summary_prompt.txt}}` |
| `json` | `{{HYDRATE:json:path/to/file.json}}` | JSON file contents stringified | `{{HYDRATE:json:common/prompts/data_summary_schema.json}}` |
| `html` | `{{HYDRATE:html:path/to/file.html}}` | HTML/text file contents as escaped string | `{{HYDRATE:html:common/templates/report_email.template.txt}}` |
| `js` | `{{HYDRATE:js:path/to/file.js}}` | JavaScript file contents (with DEHYDRATE markers) | `{{HYDRATE:js:common/functions/process_excel_data.js}}` |
| `uuid` | `{{HYDRATE:uuid:identifier}}` | Fresh UUID v4 (unique per environment) | `{{HYDRATE:uuid:schedule-trigger-id}}` |

> **Why UUID placeholders?** n8n uses trigger node IDs (especially `webhookId`) to register webhook and schedule listeners. If dev and prod workflows on the same instance share identical trigger IDs, they collide -- one overwrites the other. Fresh UUIDs per environment prevent this. During resync, UUIDs are replaced back with placeholders to keep templates portable.

### Directory Structure

```
n8n-scaffolder-for-coding-agents/
|-- n8n/
|   |-- workflows/                  # Workflow templates (*.template.json)
|   |   |-- generated/              # Hydrated output (gitignored)
|   |-- build_scripts/              # Hydration engine
|   |   |-- hydrate_workflow.py     # Hydrate a single template
|   |   |-- hydrate_all.py          # Hydrate all templates
|   |   |-- env_config.py           # YAML config loader
|   |   |-- env_hydrator.py         # {{HYDRATE:env:...}} resolver
|   |   |-- file_hydrator.py        # {{HYDRATE:txt/json/html:...}} resolver
|   |   |-- js_hydrator.py          # {{HYDRATE:js:...}} resolver
|   |   |-- uuid_hydrator.py        # {{HYDRATE:uuid:...}} resolver
|   |   |-- hydrate_validator.py    # Post-hydration validation
|   |-- deployment_scripts/         # Deploy and bootstrap
|   |   |-- deploy_workflow.sh      # Deploy single workflow
|   |   |-- deploy_all.sh           # Deploy all (tier-ordered)
|   |   |-- bootstrap_workflows.py  # Create placeholder workflows in n8n
|   |   |-- deactivate_all.sh       # Deactivate all workflows
|   |-- resync_scripts/             # Resync from n8n back to templates
|   |   |-- resync_workflow.sh      # Resync single workflow
|   |   |-- resync_all.sh           # Resync all workflows
|   |-- environments/               # Per-environment YAML configs
|   |   |-- dev.yaml
|   |   |-- prod.yaml
|   |-- deployment_order.yaml       # Tier-based deployment order
|-- common/
|   |-- prompts/                    # AI prompt files (*_prompt.txt, *_schema.json)
|   |-- functions/                  # Shared JavaScript for n8n Code nodes
|   |-- templates/                  # Email/HTML templates
|-- cloud_functions/                # FastAPI cloud function service
|   |-- app.py                      # FastAPI application
|   |-- registry.py                 # Function registry
|   |-- functions/                  # Pure Python functions
|   |-- railway.toml                # Railway deployment config
|-- scripts/
|   |-- test_hello_world.py         # Sample test script
|   |-- prompt_engineering/         # DSPy prompt optimization
|-- .env.example                    # Template for secrets
|-- .env.dev.example                # Template for dev secrets
|-- setup.sh                        # Interactive setup wizard
|-- requirements.txt                # Python dependencies
```

## Environment Management

### YAML Configuration

Each environment has a YAML config file in `n8n/environments/`:

```yaml
name: dev
displayName: "Development"
workflowNamePostfix: " [DEV]"

sharepoint:
  driveId: "your-drive-id"
  paths:
    reportFile: "/Reports/data.xlsx"

credentials:
  msOauth:
    id: "your-credential-id"
    name: "dev_ms_oauth"

cloudFunction:
  apiUrl: "https://your-service.up.railway.app"

n8n:
  instanceName: "your-instance.app.n8n.cloud"

workflows:
  periodic_excel_report:
    id: "12345"
    name: "Periodic Excel Report"
```

### .env Secrets

API keys and secrets go in `.env.<env>` files (gitignored):

```
N8N_API_KEY=your_api_key_here
```

### Adding a New Environment

1. Copy an existing YAML config: `cp n8n/environments/dev.yaml n8n/environments/staging.yaml`
2. Update the `name`, `displayName`, `workflowNamePostfix`, instance URL, credentials, and workflow IDs
3. Create a `.env.staging` file with the API key
4. Bootstrap workflows: `python3 n8n/deployment_scripts/bootstrap_workflows.py staging`

## Workflow Development

### Creating a New Workflow Template

1. Create `n8n/workflows/my_workflow.template.json` with placeholder syntax
2. Add the workflow to `n8n/environments/dev.yaml` (and other envs) under `workflows:`
3. Add it to `n8n/deployment_order.yaml` in the appropriate tier
4. Bootstrap to create the placeholder in n8n: `python3 n8n/deployment_scripts/bootstrap_workflows.py dev`
5. Hydrate and deploy: `cd n8n/deployment_scripts && ./deploy_workflow.sh dev my_workflow`

### Placeholder Syntax

Use placeholders in template JSON values:

```json
{
  "id": "{{HYDRATE:uuid:my-trigger-id}}",
  "parameters": {
    "driveId": "{{HYDRATE:env:sharepoint.driveId}}",
    "jsCode": "{{HYDRATE:js:common/functions/my_code.js}}",
    "prompt": "{{HYDRATE:txt:common/prompts/my_prompt.txt}}",
    "schema": "{{HYDRATE:json:common/prompts/my_schema.json}}"
  },
  "credentials": {
    "oAuth2Api": {
      "id": "{{HYDRATE:env:credentials.msOauth.id}}",
      "name": "{{HYDRATE:env:credentials.msOauth.name}}"
    }
  }
}
```

### Naming Conventions

- Templates: `{workflow_key}.template.json`
- Workflow keys: `snake_case` matching the YAML config key
- Generated files: `generated/{env}/{workflow_key}.generated.json`

## Deployment

### Deploy a Single Workflow

```bash
cd n8n/deployment_scripts
./deploy_workflow.sh dev periodic_excel_report
./deploy_workflow.sh prod periodic_excel_report
```

This hydrates the template, uploads the generated JSON via the n8n API, and activates the workflow.

### Deploy All Workflows

```bash
cd n8n/deployment_scripts
./deploy_all.sh dev              # Deploys all, then deactivates (dev safety)
./deploy_all.sh dev --keep-active  # Deploys all, keeps active
./deploy_all.sh prod             # Deploys all, keeps active
```

Workflows are deployed in the order defined in `n8n/deployment_order.yaml` (tier 1 first, then tier 2, etc.) to respect dependencies between workflows.

### Deployment Order

Edit `n8n/deployment_order.yaml` to define tiers:

```yaml
tiers:
  - name: "Tier 1: Leaf Subworkflows"
    workflows:
      - lock_acquiring
      - data_extraction
  - name: "Tier 2: Orchestrators"
    workflows:
      - main_pipeline
```

### Bootstrapping

Before deploying for the first time in a new environment, create placeholder workflows:

```bash
python3 n8n/deployment_scripts/bootstrap_workflows.py dev
python3 n8n/deployment_scripts/bootstrap_workflows.py prod --dry-run
```

This creates empty workflows in n8n via the API and records the assigned IDs in the environment YAML.

## Resync

Resync pulls live workflow state from n8n and dehydrates it back into a template.

### Resync a Single Workflow

```bash
cd n8n/resync_scripts
./resync_workflow.sh dev periodic_excel_report
```

### Resync All Workflows

```bash
cd n8n/resync_scripts
./resync_all.sh dev
```

Auto-discovers all workflow keys from the environment YAML and resyncs each one.

### Dehydration

During resync, the dehydration process:
- Removes runtime metadata (updatedAt, createdAt, versionId, etc.)
- Restores placeholder syntax where values match known patterns
- Preserves nodes, connections, and settings

## Cloud Functions

The `cloud_functions/` directory contains a FastAPI service that exposes pure Python functions as HTTP endpoints, callable from n8n HTTP Request nodes.

### Local Development

```bash
cd cloud_functions
pip install -r requirements.txt
python app.py
# Server runs at http://localhost:8000
# Health check: GET /health
# Functions: GET /hello_world?name=World
```

### Railway Deployment

The service is pre-configured for Railway deployment with `railway.toml` and `railpack.json`. Set the root directory to `cloud_functions/` in your Railway service settings.

### Adding a New Function

1. Create `cloud_functions/functions/my_function.py`:
   ```python
   def my_function(input_data: str = "default") -> dict:
       """My cloud function."""
       return {"result": process(input_data)}
   ```
2. Register it in `cloud_functions/registry.py`:
   ```python
   from functions.my_function import my_function
   EXPOSED_FUNCTIONS = {
       "hello_world": hello_world,
       "my_function": my_function,
   }
   ```
3. The endpoint is automatically available at `GET /my_function`

### Testing

```bash
python scripts/test_hello_world.py
```

## Prompt Engineering

The `scripts/prompt_engineering/` directory provides a DSPy-based framework for evaluating and optimizing prompts stored in `common/prompts/`.

### Overview

1. **Define signatures** matching your JSON schemas in `common/prompts/`
2. **Create evaluation datasets** with expected inputs and outputs
3. **Run optimization** using DSPy optimizers (MIPROv2, BootstrapFewShot, etc.)
4. **Export optimized prompts** back to `common/prompts/` files

### Example

```bash
cd scripts/prompt_engineering
pip install -r requirements.txt
python example_signature.py
```

### Supported Providers

Configure in `.env` or environment variables:
- **OpenAI** (default): `OPENAI_API_KEY`
- **OpenRouter**: `OPENROUTER_API_KEY`
- **Anthropic**: `ANTHROPIC_API_KEY`

## Commands Reference

| Command | Description |
|---------|-------------|
| `bash setup.sh` | Interactive first-time setup |
| `python3 n8n/build_scripts/hydrate_workflow.py -e dev -t <template> -k <key>` | Hydrate a single template |
| `python3 n8n/build_scripts/hydrate_all.py -e dev` | Hydrate all templates |
| `./n8n/deployment_scripts/deploy_workflow.sh dev <key>` | Deploy a single workflow |
| `./n8n/deployment_scripts/deploy_all.sh dev` | Deploy all workflows (tier-ordered) |
| `./n8n/deployment_scripts/deploy_all.sh dev --keep-active` | Deploy all, keep active in dev |
| `python3 n8n/deployment_scripts/bootstrap_workflows.py dev` | Create placeholder workflows |
| `./n8n/deployment_scripts/deactivate_all.sh dev` | Deactivate all workflows |
| `./n8n/resync_scripts/resync_workflow.sh dev <key>` | Resync a single workflow |
| `./n8n/resync_scripts/resync_all.sh dev` | Resync all workflows |
| `python3 cloud_functions/app.py` | Run cloud functions locally |
| `python3 scripts/prompt_engineering/example_signature.py` | Run DSPy example |

## Comparison with Manual Approach

| Task | Manual Approach | With This Scaffolding |
|------|----------------|----------------------|
| Multi-env deploy | Copy-paste JSON, manually change credentials and IDs | `./deploy_all.sh prod` |
| Update a prompt | Edit JSON string in n8n UI, copy to other envs | Edit `common/prompts/file.txt`, deploy |
| Add a credential | Find every reference in every workflow JSON | Change one YAML value, redeploy |
| Sync UI changes | Export JSON, manually diff, copy to repo | `./resync_all.sh dev` |
| New environment | Recreate every workflow from scratch | Copy YAML + bootstrap + deploy |
| Version control | Giant JSON diffs with UUIDs and metadata noise | Clean templates with readable placeholders |
| Cloud function | Write a full server, configure routes | Add a function, register it, done |
| Prompt optimization | Trial and error in the n8n UI | DSPy evaluation with metrics |
