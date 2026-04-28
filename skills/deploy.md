---
description: Hydrate, PUT to n8n, and (default) activate one workflow on one env.
---

# deploy

## When

Roll one workflow to one env.

## How

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/helpers/deploy.py --env <env> --workflow-key <key> [--no-activate] [--rehydrate] [--debug]
```

## Side effects

1. Calls `hydrate.py` first (composes; produces `<workspace>/n8n-build/<env>/<key>.generated.json`) if missing or `--rehydrate`.
2. Reads the generated JSON, drops disallowed PUT fields (active, tags, id, versionId), PUTs to `<base>/api/v1/workflows/<id>`.
3. By default, activates via `POST /workflows/<id>/activate`. `--no-activate` skips this.
4. With `--debug`, dumps redacted pre/post artifacts to `~/.cache/n8n-harness/debug/<pid>/deploy-<n>.json` (mode 0600).

## Pattern

See `skills/patterns/validate-deploy.md` for the canonical 5-step loop.

## See also

- [`skills/patterns/agent-api-discipline.md`](patterns/agent-api-discipline.md) — verify `PUT /workflows/{id}` accepted-fields list and `/activate` response shape via Context7 before assuming training-data recall is current.
