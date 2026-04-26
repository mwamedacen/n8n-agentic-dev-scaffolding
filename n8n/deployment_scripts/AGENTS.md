# n8n Deployment Scripts

## Quick reference

```bash
./deploy_all.sh dev                                # all, deactivates after (safety)
./deploy_all.sh dev --keep-active                  # all, keep active
./deploy_workflow.sh dev <workflow_key>            # single workflow
./deploy_all.sh prod                               # all, keep active
python3 bootstrap_workflows.py dev                 # mint placeholder workflow IDs
./deactivate_all.sh dev                            # deactivate all in env
```

The Python equivalents (preferred for agents) are `helpers.deploy(key, env=None, activate=True)`, `helpers.deactivate(key, env=None)`, `helpers.bootstrap(env=None)`. The harness deliberately omits `deploy_all` / `deactivate_all` Python helpers — agents compose loops; bash scripts keep their role for non-agent ergonomics.

## deploy_workflow.sh

```bash
./deploy_workflow.sh <env> <workflow_key>
```

1. Loads the env config + secrets (root `.env` first, then `.env.<env>` overlay; env-specific WINS).
2. Hydrates `n8n/workflows/<workflow_key>.template.json` via `hydrate_workflow.py`.
3. PUTs the generated JSON to `/api/v1/workflows/{id}`.
4. POSTs `/api/v1/workflows/{id}/activate`.

## deploy_all.sh

Reads tiers from `n8n/deployment_order.yaml` and deploys each workflow in tier order. Tier 1 first, then tier 2, etc. Within a tier order is unspecified.

For `dev`: automatically deactivates all workflows after deploy (safety — prevents dev schedules/webhooks from firing while you set up). Override with `--keep-active`. Non-dev envs keep things active.

## deployment_order.yaml

```yaml
tiers:
  - name: "Tier 1: Leaf subworkflows"
    workflows:
      - lock_acquiring
      - data_extraction
  - name: "Tier 2: Pipelines that call them"
    workflows:
      - main_pipeline
```

**Why tiers matter:** Execute Workflow nodes need the callee's ID. Place callees in earlier tiers. See `pattern-skills/subworkflows.md`.

## bootstrap_workflows.py

Creates empty placeholder workflows for every key in YAML that doesn't already have a real ID, and records the n8n-assigned IDs back into the YAML.

```bash
python3 bootstrap_workflows.py dev          # real
python3 bootstrap_workflows.py prod --dry-run
```

Skips entries whose `id` is empty, `null`, `placeholder`, or starts with `your-`. Run after adding new workflows to YAML.

## .env layering

Both `_common.sh` and `bootstrap_workflows.py` source root `.env` first, then `.env.<env>` with overlay semantics — env-specific values WIN for shared keys. This matches `admin._load_env` so Python helpers and bash agree.

## YAML structure

```yaml
name: dev
displayName: "Development"
workflowNamePostfix: " [DEV]"

n8n:
  instanceName: "your-instance.app.n8n.cloud"

credentials:
  msOauth: { id: "...", name: "dev_ms_oauth" }

workflows:
  periodic_excel_report:
    id: "12345"          # set by bootstrap
    name: "Periodic Excel Report"
```

## Troubleshooting

| Error | Likely cause |
|---|---|
| `N8N_API_KEY is not set` | Set in root `.env` or `.env.<env>`. |
| `Environment config not found` | YAML missing — `ls n8n/environments/`. |
| `Template file not found` | Naming: `n8n/workflows/<key>.template.json`. |
| `Workflow key not found or has no id` | Add to YAML, then run `bootstrap_workflows.py`. |
| `HTTP 404` on PUT | Stale ID; re-bootstrap or fix YAML. |
| `HTTP 401` | Expired/invalid `N8N_API_KEY`; rotate in n8n UI. |
| `Upload OK but activation failed` | Credential `name` in YAML doesn't match n8n's exact credential name. See `pattern-skills/credential-refs.md`. |
