# Local n8n via Docker

## When to use

When you want a throwaway n8n instance to test workflows without touching a hosted account — e.g., reproducing a bug, smoke-testing before pushing, or working offline.

## Prerequisites

- Docker Desktop or compatible Docker engine.
- Port 5678 free (or pick another with `port=` argument).

## Mechanics

```python
start_local_n8n("local")  # starts container, prints URL
# user opens http://localhost:5678 in browser, creates owner account, mints API key
attach("local", base_url="http://localhost:5678", api_key="...")
list_workflows(env="local")  # empty on a fresh instance
# ...do work...
detach("local")
stop_local_n8n("local")
```

## Why a manual API-key step

n8n's owner-account creation is a UI flow on first run. The OWNER cookie is set by the browser after accepting the EULA + setting a password; the public-API key is then minted in Settings > API. There is no documented bootstrap shortcut to mint that without UI interaction.

`start_local_n8n()` prints the URL and walks you through the steps; you take it from there. Once the API key is in hand, the `attach()` call is identical to attaching to a hosted instance.

## Idempotency

- `start_local_n8n()` checks if a container named `n8n-harness-<env>` is already running and returns without re-creating it.
- `stop_local_n8n()` calls `docker stop` and tolerates "not running" as already-stopped.

## Gotchas

- **`docker not on PATH`:** Doctor flags Docker as a soft dependency. `start_local_n8n()` raises explicitly if Docker isn't available — no silent retries.
- **Port collision:** if 5678 is taken, pass `port=5679` (or whatever free port). `attach()` uses the URL you give it, so they must agree.
- **Data persistence:** the default `n8nio/n8n` image stores its SQLite DB inside the container. `--rm` (which we set) wipes it on stop. For persistent local workflows, mount a volume yourself: `docker run -v ~/.n8n-local:/home/node/.n8n ...` outside the harness, then `attach()` to the running URL.
- **Self-signed TLS:** if you run n8n on `https://localhost:443` with a self-signed cert, n8n-harness's HTTP calls will reject it. Stick to `http://localhost:<port>` for local Docker.

## See also

- `pattern-skills/remote-attach.md` — for the attach API itself.
- `helpers.start_local_n8n()` and `helpers.stop_local_n8n()` — the function bodies.
