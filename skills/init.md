---
name: init
description: Scaffold a fresh n8n-harness workspace at ${PWD}/n8n-harness-workspace/.
---

# init

## When

First-time use of n8n-harness in a project, or to reset from a clean slate.

## How

```bash
python3 <harness>/helpers/init.py
```

Optional flags:

- `--workspace <path>`: override default `${PWD}/n8n-harness-workspace`
- `--force`: clobber existing workspace (DESTRUCTIVE — confirm with the user)

## Side effects

Creates the workspace tree:

- `n8n-config/` — env YAML + `.env.<env>` files (initially with `.env.example`)
- `n8n-workflows-template/` — `*.template.json` (canonical, version-controlled)
- `n8n-build/` — hydrated outputs (gitignored)
- `n8n-prompts/{prompts,datasets,evals}/`
- `n8n-functions/{js,py}/`, `n8n-functions-tests/`
- `n8n-assets/{email-templates,images,misc}/`
- `cloud-functions/{,functions/}`, `cloud-functions-tests/`
- `N8N-HARNESS-MEMORY.md` (agent persistent memory)
- `.gitignore` (`n8n-build/`, `.env.*`)

## Idempotence

Refuses to clobber an existing workspace. Pass `--force` to recreate (DESTRUCTIVE).

## Next step

Run `bootstrap-env.md` to configure your first environment.
