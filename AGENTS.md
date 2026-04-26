# n8n harness

## Git Commit Policy

NEVER commit changes without explicit authorization from the user. Always ask before committing.

## Project Overview

This is a scaffolding for developing n8n workflows as code. It provides:

- Template-based workflow authoring with placeholder hydration
- Multi-environment configuration (dev, prod (add more by creating YAML + .env files))
- Automated deployment and resync scripts
- Cloud functions service (FastAPI on Railway)
- DSPy-based prompt engineering

## Project Structure

```
n8n/
  workflows/          # *.template.json files (version controlled)
  build_scripts/      # Hydration engine (Python)
  deployment_scripts/ # Deploy, bootstrap, deactivate (Bash + Python)
  resync_scripts/     # Resync and dehydrate (Bash + Python)
  environments/       # Per-env YAML configs (dev.yaml, prod.yaml)
  deployment_order.yaml
common/
  prompts/            # *_prompt.txt and *_schema.json files
  functions/          # Shared JS for n8n Code nodes
  templates/          # Email/HTML templates
cloud_functions/      # FastAPI service
  functions/          # Pure Python functions
factory/
  prompt_engineering/ # DSPy optimization
```

## Multi-Environment System

Each environment has:
- **YAML config** (`n8n/environments/{env}.yaml`): Instance URL, credentials, workflow IDs, resource paths
- **Secrets file** (`.env.{env}`): API keys (gitignored)

Templates are hydrated into `n8n/workflows/generated/{env}/` (gitignored).

## Placeholder Types

Templates use these placeholder types, resolved during hydration:

| Type | Syntax | Source | Example |
|------|--------|--------|---------|
| `env` | `{{HYDRATE:env:key.path}}` | YAML config value (dot notation) | `{{HYDRATE:env:sharepoint.driveId}}` |
| `txt` | `{{HYDRATE:txt:relative/path.txt}}` | Text file contents | `{{HYDRATE:txt:common/prompts/data_summary_prompt.txt}}` |
| `json` | `{{HYDRATE:json:relative/path.json}}` | JSON file contents (stringified) | `{{HYDRATE:json:common/prompts/data_summary_schema.json}}` |
| `html` | `{{HYDRATE:html:relative/path.html}}` | HTML/template file contents | `{{HYDRATE:html:common/templates/report_email.template.txt}}` |
| `js` | `{{HYDRATE:js:relative/path.js}}` | JavaScript file contents | `{{HYDRATE:js:common/functions/process_excel_data.js}}` |
| `uuid` | `{{HYDRATE:uuid:identifier}}` | Fresh UUID v4 each hydration | `{{HYDRATE:uuid:schedule-trigger-id}}` |

## Quick Commands

```bash
# Deploy all workflows to dev
cd n8n/deployment_scripts && ./deploy_all.sh dev

# Deploy a single workflow to prod
cd n8n/deployment_scripts && ./deploy_workflow.sh prod periodic_excel_report

# Hydrate all templates for dev
cd n8n/build_scripts && python3 hydrate_all.py -e dev

# Resync all workflows from dev
cd n8n/resync_scripts && ./resync_all.sh dev

# Deactivate all dev workflows
cd n8n/deployment_scripts && ./deactivate_all.sh dev

# Bootstrap placeholder workflows
python3 n8n/deployment_scripts/bootstrap_workflows.py dev
```

## Subdirectory Documentation

Each major directory has its own AGENTS.md with detailed context:

- `n8n/workflows/AGENTS.md` -- Template format, placeholder syntax, naming conventions
- `n8n/build_scripts/AGENTS.md` -- Hydration pipeline, helper modules
- `n8n/deployment_scripts/AGENTS.md` -- Deploy, bootstrap, deactivate scripts
- `n8n/resync_scripts/AGENTS.md` -- Resync and dehydration process
- `cloud_functions/AGENTS.md` -- FastAPI service, Railway setup
- `cloud_functions/functions/AGENTS.md` -- Pure function guidelines
- `common/prompts/AGENTS.md` -- Prompt and schema conventions
- `factory/AGENTS.md` -- Test scripts and prompt engineering

## Recommended MCP Servers

- **Context7**: Use for fetching up-to-date documentation for libraries used in this project (DSPy, FastAPI, n8n, Redis, OpenAI, LiteLLM). Prefer Context7 over web search for library docs — training data may not reflect recent API changes.

## General Principles

- **n8n Compatibility**: All generated JSON must be valid for n8n's import/API. Use `connections` keyed by node name, proper `typeVersion` values, and valid credential references.
- **Data Formatting**: Numbers use appropriate precision. Strings are properly escaped in JSON context. JavaScript in Code nodes must be valid ES2020+.
- **Testing**: After changing prompts, run evaluations. After changing templates, hydrate and verify. After changing cloud functions, run the test scripts.
- **No pinData in Templates**: Never include `pinData` in template files -- it contains test data and should only exist in the n8n UI.

## Prompt Engineering

The `factory/prompt_engineering/` directory uses DSPy for prompt optimization:

1. Define **signatures** matching your `common/prompts/` schemas
2. Build **evaluation datasets** with expected inputs/outputs
3. Run **DSPy optimizers** (MIPROv2, BootstrapFewShot) to find better prompts
4. Export optimized prompts back to `common/prompts/` files

Configure LM provider in `.env`: `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, or `ANTHROPIC_API_KEY`.
