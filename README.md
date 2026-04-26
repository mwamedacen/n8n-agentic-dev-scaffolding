# n8n-harness

Direct n8n control via REST + MCP. The thin attach-style harness for authoring, deploying, running, and resyncing n8n workflows as code. Inspired by `browser-use/browser-harness`.

## Install

```bash
git clone <repo-url>
cd n8n-harness
uv tool install -e .
n8n-harness --setup
```

`--setup` is interactive: it asks for `N8N_INSTANCE_NAME`, `N8N_API_KEY`, and `OPENROUTER_API_KEY`, writes them to root `.env`, then validates by hitting `GET /api/v1/workflows`. See `install.md` for prerequisites and troubleshooting.

## Usage

```bash
n8n-harness -c "
hydrate('demo_smoke')
deploy('demo_smoke', activate=True)
ex = run_workflow('demo_smoke')
print(wait_for_execution(ex['id']))
"
```

Helpers, `os`, `json`, `sys` are pre-imported in the snippet's scope. Read `SKILL.md` for the default workflow and design constraints.

## Layout

```
n8n/
  workflows/          *.template.json (canonical, version-controlled)
  build_scripts/      hydration engine
  deployment_scripts/ deploy / bootstrap / deactivate
  resync_scripts/     resync / dehydrate
  environments/       per-env YAML configs (dev.yaml, prod.yaml)
common/
  prompts/            *_prompt.txt + *_schema.json
  functions/          shared JS for n8n Code nodes
  templates/          email / HTML templates
cloud_functions/      optional FastAPI service for HTTP-callable Python
factory/
  prompt_engineering/ DSPy optimization (OpenRouter default)
pattern-skills/       agent-authored authoring patterns
integration-skills/   per-service quirks (microsoft-365, gmail, redis, ...)
helpers.py            agent toolbox — read, edit, extend
admin.py              env layering, client cache, doctor, setup, update
run.py                tiny CLI entrypoint (manual flag parsing, no argparse)
```

## Multi-environment

Root `.env` is the base; `.env.<env>` overlays on top with `override=True` — env-specific values WIN for shared keys. YAML configs (`n8n/environments/<env>.yaml`) hold non-secret values: instance URL, credential IDs, workflow IDs, resource paths.

```bash
n8n-harness --env prod -c "..."
n8n-harness --list-envs
```

To add an environment: `cp n8n/environments/dev.yaml n8n/environments/staging.yaml`, optionally create `.env.staging`, then `n8n-harness --env staging -c "bootstrap()"`.

## Verification

```bash
n8n-harness --doctor          # checks env vars, API reach, MCP, YAML, templates
n8n-harness --version
n8n-harness --reload          # clear client cache, re-source .env
n8n-harness --update -y       # git pull / uv tool upgrade (refuses dirty worktree)
n8n-harness --debug-deploys -c "deploy('k')"  # dump redacted artifact under ~/.cache/n8n-harness/
```

## When n8n's REST is the wrong tool

n8n's public REST does NOT support `/workflows/{id}/run`. `run_workflow()` works only on workflows with a Webhook trigger — it POSTs to the workflow's webhook path then polls `/executions`. Manual-trigger and chat-trigger workflows must be tested in the n8n UI.

## Comparison to browser-harness

| browser-harness | n8n-harness |
|---|---|
| Attach to running Chrome via CDP | Attach to running n8n via REST + MCP |
| `helpers.py` (browser primitives) | `helpers.py` (workflow CRUD, hydrate/deploy/resync, llm wrapper) |
| `domain-skills/<host>/` | `integration-skills/<service>/` |
| `interaction-skills/` | `pattern-skills/` |
| `daemon.py` | (none — REST is request/response) |
| `coordinate clicks` | hydrate-first deploy + validate-before-deploy |

Deliberate deviations are catalogued in `n8n-harness-plan.md` §6.

## License

MIT — see `LICENSE`.
