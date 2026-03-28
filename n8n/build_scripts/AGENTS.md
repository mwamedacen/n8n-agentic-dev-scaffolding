# n8n Build Scripts

## Hydration Pipeline

The hydration process resolves placeholders in a fixed order. This order matters because later steps may depend on earlier ones.

1. **File placeholders** (`txt`, `json`, `html`) -- Inline file contents into the template
2. **JS placeholders** (`js`) -- Inline JavaScript file contents with DEHYDRATE marker support
3. **ENV placeholders** (`env`) -- Resolve values from the environment YAML config
4. **UUID placeholders** (`uuid`) -- Generate fresh UUIDs for trigger nodes
5. **Name resolution** -- Set the workflow name with the environment postfix (e.g., "My Workflow [DEV]")
6. **Validation** -- Check that no unresolved `{{HYDRATE:...}}` placeholders remain

## Placeholder Types

| Type | Pattern | Source | Example |
|------|---------|--------|---------|
| `env` | `{{HYDRATE:env:key.path}}` | YAML config dot-path | `{{HYDRATE:env:sharepoint.driveId}}` |
| `txt` | `{{HYDRATE:txt:path}}` | Text file (prompts) | `{{HYDRATE:txt:common/prompts/data_summary_prompt.txt}}` |
| `json` | `{{HYDRATE:json:path}}` | JSON file (schemas) | `{{HYDRATE:json:common/prompts/data_summary_schema.json}}` |
| `html` | `{{HYDRATE:html:path}}` | HTML/template file | `{{HYDRATE:html:common/templates/report_email.template.txt}}` |
| `js` | `{{HYDRATE:js:path}}` | JavaScript file | `{{HYDRATE:js:common/functions/process_excel_data.js}}` |
| `uuid` | `{{HYDRATE:uuid:id}}` | Generated UUID v4 | `{{HYDRATE:uuid:schedule-trigger-id}}` |

## Script Usage

### hydrate_workflow.py (Single Workflow)

The generic hydrator that replaces per-workflow hydration scripts. Takes environment, template path, and workflow key as arguments.

```bash
python3 hydrate_workflow.py -e dev -t n8n/workflows/periodic_excel_report.template.json -k periodic_excel_report
python3 hydrate_workflow.py -e prod -t n8n/workflows/my_workflow.template.json -k my_workflow
```

Arguments:
- `-e, --env`: Environment name (dev, prod, etc.)
- `-t, --template`: Path to the template file (relative or absolute)
- `-k, --key`: Workflow key matching the key in the environment YAML

Output: `n8n/workflows/generated/{env}/{key}.generated.json`

### hydrate_all.py (All Workflows)

Auto-discovers all `*.template.json` files in `n8n/workflows/` and hydrates each one.

```bash
python3 hydrate_all.py -e dev
python3 hydrate_all.py -e prod
python3 hydrate_all.py -e dev -v  # verbose output
```

Discovery convention: `{workflow_key}.template.json` extracts the key from the filename.

## Helper Modules

### env_config.py
- `load_env_config(env_name)` -- Load and validate a YAML config file
- `get_config_value(config, 'dot.path')` -- Access nested values by dot notation
- `list_available_environments()` -- List all `*.yaml` files in `n8n/environments/`
- `flatten_config(config)` -- Flatten nested dict to dot-notation keys
- `validate_config(config)` -- Check required keys (name, displayName, n8n.instanceName, workflow entries)

### env_hydrator.py
- `resolve_env_placeholders(data, config)` -- Replace all `{{HYDRATE:env:...}}` with config values
- `find_env_placeholders(data)` -- List all env placeholders in a workflow
- `validate_all_placeholders_resolvable(data, config)` -- Check all placeholders have values

### file_hydrator.py
- `resolve_file_placeholders(data, base_dir)` -- Replace `{{HYDRATE:txt/json/html:...}}` with file contents
- `find_file_placeholders(data)` -- List all file placeholders

### js_hydrator.py
- `resolve_js_placeholders(data, base_dir)` -- Replace `{{HYDRATE:js:...}}` with JS file contents
- `find_js_placeholders(data)` -- List all JS placeholders
- Supports `// DEHYDRATE:START` / `// DEHYDRATE:END` markers for round-trip editing

### uuid_hydrator.py
- `resolve_uuid_placeholders(data)` -- Replace `{{HYDRATE:uuid:...}}` with fresh UUIDs
- `find_uuid_placeholders(data)` -- List all UUID placeholders

### hydrate_validator.py
- `validate_no_placeholders(filepath, data)` -- Verify no `{{HYDRATE:...}}` patterns remain in the output

## When to Regenerate

Re-run hydration when:
- A prompt file in `common/prompts/` changes
- A JSON schema in `common/prompts/` changes
- A JavaScript function in `common/functions/` changes
- An HTML template in `common/templates/` changes
- Environment YAML config values change (credentials, resource paths, etc.)
- The workflow template itself changes

Deploy scripts auto-regenerate before uploading, so a standalone regeneration is typically only needed for inspection or debugging.

## Node Positions After Template Changes

When modifying a workflow template (adding/removing/reordering nodes), **recalculate all downstream node positions**. n8n does NOT auto-layout — incorrect positions cause nodes to overlap in the UI. See `n8n/workflows/AGENTS.md` for the full positioning rules.

## How to Add a New Workflow

1. Create `n8n/workflows/{workflow_key}.template.json`
2. Add the workflow entry to each environment YAML in `n8n/environments/`:
   ```yaml
   workflows:
     my_new_workflow:
       id: "placeholder"
       name: "My New Workflow"
   ```
3. Add it to `n8n/deployment_order.yaml` in the appropriate tier
4. Bootstrap: `python3 ../deployment_scripts/bootstrap_workflows.py dev`
5. Hydrate: `python3 hydrate_workflow.py -e dev -t n8n/workflows/my_new_workflow.template.json -k my_new_workflow`
6. Deploy: `cd ../deployment_scripts && ./deploy_workflow.sh dev my_new_workflow`
