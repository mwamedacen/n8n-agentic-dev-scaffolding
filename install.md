# Installing n8n-harness

## Prerequisites

- Python ≥ 3.11
- `uv` (recommended) — install: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- An n8n instance you control: a hosted account at `<workspace>.app.n8n.cloud` or a self-hosted instance reachable over HTTP. You'll need an API key from Settings → API.

## Install

```bash
git clone <repo-url>
cd n8n-harness
uv tool install -e .
n8n-harness --setup
```

`--setup` is interactive: it prompts for `N8N_INSTANCE_NAME`, `N8N_API_KEY`, and `OPENROUTER_API_KEY`, writes them to root `.env`, then validates by hitting `GET /api/v1/workflows`.

If you don't have `uv`, the included `setup.sh` falls back to `pip install --user -e .` and then runs `n8n-harness --setup`.

## Verify

```bash
n8n-harness --doctor
```

Should print:

```
n8n-harness doctor
  ...
  [ok  ] N8N_API_KEY
  [ok  ] N8N_INSTANCE_NAME
  [ok  ] OPENROUTER_API_KEY
  [ok  ] API reachable — HTTP 200
  ...
```

Exit code 0 means you're ready.

## First steps

```bash
# What workflows does my n8n have?
n8n-harness -c "print(json.dumps(list_workflows(), indent=2))"

# Deploy the smoke fixture and run it
n8n-harness -c "
hydrate('demo_smoke')
deploy('demo_smoke', activate=True)
ex = run_workflow('demo_smoke')
print(wait_for_execution(ex['id']))
"
```

If `list_workflows()` shows entries with `key=null`, those are workflows in your n8n that don't yet exist in `n8n/environments/<env>.yaml`. That's fine — `key=null` is "not yet tracked", not "broken".

## Multi-environment setup

Each environment has a YAML config in `n8n/environments/<env>.yaml` plus an optional `.env.<env>` overlay. `dev` is the default; `prod.yaml` ships pre-configured but with placeholder IDs.

To add a `staging` environment:

1. `cp n8n/environments/dev.yaml n8n/environments/staging.yaml`
2. Update `name`, `displayName`, `workflowNamePostfix`, instance URL, credentials, workflow IDs.
3. Optionally create `.env.staging` to override the root `.env` — env-specific values WIN for shared keys.
4. `n8n-harness --env staging -c 'bootstrap()'` to create empty placeholder workflows in n8n with the new env's name postfix.

## Updating

```bash
n8n-harness --update -y
```

Refuses to update on a dirty worktree (commit or stash first).

## Reload after credential rotation

```bash
n8n-harness --reload
```

Clears the cached `N8nClient` and re-sources `.env` on next call. Useful after rotating `N8N_API_KEY` without restarting your shell.

## Troubleshooting

### `--doctor` reports `API reachable — FAIL`

- Check `N8N_INSTANCE_NAME`. Hosted: `myname.app.n8n.cloud`. Self-hosted: include the protocol if non-default (`http://localhost:5678`).
- Check that `N8N_API_KEY` hasn't expired. Rotate in Settings → API in the n8n UI.
- Try a raw curl: `curl -H "X-N8N-API-KEY: $N8N_API_KEY" https://$N8N_INSTANCE_NAME/api/v1/workflows`

### `deploy()` returns HTTP 404

The workflow ID in `n8n/environments/<env>.yaml` doesn't exist on your instance. Run `n8n-harness -c "bootstrap()"` to create empty placeholders, or fix the YAML id manually.

### `run_workflow()` says "no Webhook trigger"

n8n's public REST API does not support `/workflows/{id}/run`. `run_workflow()` only works on workflows that have a Webhook trigger. Add one (manual triggers can only fire from the UI).

### `--setup` wrote `.env` but doctor still fails

Maybe an env var was set in your shell from a previous session. Run `unset N8N_API_KEY N8N_INSTANCE_NAME OPENROUTER_API_KEY` then re-run `--doctor`.

## Uninstall

```bash
uv tool uninstall n8n-harness
```

Or if installed via pip: `python3 -m pip uninstall n8n-harness`.

The repo's `.env`, `.env.*`, `n8n/environments/`, and `n8n/workflows/` are all left in place — you're managing your own data.
