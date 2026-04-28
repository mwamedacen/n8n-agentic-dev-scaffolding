# n8n-evol-I

A skill package for driving n8n from code. Designed to be read by a coding agent.

## Why

n8n is a capable workflow automation platform, but operating it at scale from code requires the same boilerplate on every project: REST-API wrappers, per-environment config management, a way to keep workflow logic in version control, and enough structural discipline that a coding agent can author and deploy without re-learning the API surface every session.

n8n-evol-I provides that structure. It is a read-only skill package: the agent reads markdown sub-skills from `skills/` and invokes Python helpers from `helpers/` against a separate per-project workspace. Workflow templates live in the workspace, not in the harness, so the harness can be updated with `git pull` without touching user content. The agent needs to know only one thing: read `SKILL.md` first.

## Features

- **Multi-environment workflows.** Configure dev, staging, and prod in `n8n-config/<env>.yml` with per-env instance URLs, workflow IDs, and credential refs. Every helper accepts `--env`. See [`bootstrap-env.md`](skills/bootstrap-env.md).

- **Build-time substitution keeps heavy resources out of workflow JSON.** Code, prompts, schemas, email templates, env values, and UUIDs live in dedicated workspace files (`n8n-functions/`, `n8n-prompts/`, `n8n-assets/`, `n8n-config/`). Templates reference them via `{{@:js|py|txt|json|html|env|uuid:...}}` placeholders that `hydrate.py` substitutes at deploy time; `dehydrate.py` re-extracts on resync, so round-trips with the n8n UI are byte-stable. The agent edits a 50-line `*.template.json` plus separate code/prompt/template files instead of a 200KB blob with everything inlined.

  ```jsonc
  // n8n-workflows-template/aggregate.template.json
  { "type": "n8n-nodes-base.code",
    "parameters": { "jsCode": "{{@:js:n8n-functions/js/aggregate.js}}\n\nreturn aggregate(items);" } }
  ```

  See [`skills/patterns/code-node-discipline.md`](skills/patterns/code-node-discipline.md) for the strict-mode rule on JS/Python segmentation.

- **Dependency-ordered deployment.** `deploy_all.py` rolls out an entire env in tier order so callee sub-workflows deploy before callers. Tier assignment is set per-workflow at create time via `n8n-config/deployment_order.yml`. See [`deploy_all.md`](skills/deploy_all.md).

- **Execution debugging.** `debug.md` guides a structured investigation from symptom to root cause: dependency-graph traversal, candidate pre-screening, per-execution causal-linkage checks, trigger health, blast-radius enumeration, and a prescribed sub-agent cross-check step. Backed by `list_executions.py`, `inspect_execution.py`, and `dependency_graph.py`. See [`skills/patterns/investigation-discipline.md`](skills/patterns/investigation-discipline.md).

- **Distributed locking.** Redis-backed acquire/release primitives (`lock_acquisition`, `lock_release`) with owner-pointer tracking so a crash lets the next caller identify and clean up a held scope. Locks self-heal via Redis TTL if the error handler is not configured. `add-lock-to-workflow.md` wraps any workflow in lock/release in one command. See [`skills/patterns/locking.md`](skills/patterns/locking.md).

- **Rate limiting.** Fixed-window Redis INCR primitive (`rate_limit_check`) with configurable limit, window, and denied-branch behavior (passthrough / stop / error). `add-rate-limit-to-workflow.md` gates any workflow at the head of its main flow. See [`skills/patterns/locking.md`](skills/patterns/locking.md).

- **Error handling + observability.** Three-step paradigm — capture (Error Trigger), log (Sentry / Datadog / Slack), process (lock cleanup, DB invalidation, compensating workflows). Sinks fan out in parallel branches so a single sink failing doesn't block the others. `register-workflow-to-error-handler.md` wires any workflow into a workspace's central handler. See [`skills/patterns/error-handling.md`](skills/patterns/error-handling.md) and [`skills/integrations/datadog/README.md`](skills/integrations/datadog/README.md).

- **Cloud function scaffolding.** `add-cloud-function.md` scaffolds a Python function into a FastAPI service in `cloud-functions/` and auto-registers it in the app's router. The service ships with Railway deployment config (`railpack.json`); callable from n8n via HTTP Request nodes. See [`skills/add-cloud-function.md`](skills/add-cloud-function.md).

- **Prompt optimization with DSPy.** `iterate-prompt.md` runs BootstrapFewShot or MIPROv2 against a workspace prompt + schema + dataset, evaluates on structural correctness, and optionally exports the optimized prompt back to disk. Requires `pip install dspy litellm`. See [`skills/iterate-prompt.md`](skills/iterate-prompt.md).

## Install

A harness for n8n — ships as a standalone skill set or as a Claude Code plugin with slash commands and auto-tidy. The workspace and all helpers work identically in both.

| | Skill mode | Plugin mode |
|---|---|---|
| Slash commands | No | Yes (`/n8n-evol-I:*`) |
| Auto-tidy hook | Manual opt-in | Automatic |
| Discovery | Read `SKILL.md` | Claude Code `/help` |
| Other agent runtimes | Yes | Claude Code only |

### Skill mode (works with any agent runtime)

```bash
git clone https://github.com/mwamedacen/n8n-evol-I.git ~/.claude/skills/n8n-evol-I
pip install pyyaml requests python-dotenv
```

### Plugin mode (Claude Code only)

Plugin mode adds 10 namespaced slash commands covering the full operational lifecycle — `/n8n-evol-I:deploy`, `/n8n-evol-I:deploy_all`, `/n8n-evol-I:resync`, `/n8n-evol-I:resync_all`, `/n8n-evol-I:tidyup`, `/n8n-evol-I:debug`, `/n8n-evol-I:run`, `/n8n-evol-I:doctor`, `/n8n-evol-I:validate`, `/n8n-evol-I:test` — plus an auto-tidy hook that normalizes template positions after every Edit/Write/MultiEdit.

CLI form (run in your terminal):

```bash
claude plugin install https://github.com/mwamedacen/n8n-evol-I
```

In-session form (inside a Claude Code session):

```
/plugin install https://github.com/mwamedacen/n8n-evol-I
```

Local dev:

```bash
claude --plugin-dir ./n8n-evol-I
```

## Quick start

Set `HARNESS` to your install location — these commands work in both modes:

```bash
# Skill mode:
HARNESS=~/.claude/skills/n8n-evol-I
# Plugin mode (inside a Claude Code session, this is auto-resolved):
HARNESS=$CLAUDE_PLUGIN_ROOT

python3 $HARNESS/helpers/init.py
python3 $HARNESS/helpers/bootstrap_env.py \
  --env dev --instance acme.app.n8n.cloud --api-key <key>
python3 $HARNESS/helpers/doctor.py --env dev
```

See [`install.md`](install.md) for full prerequisites, optional extras, and update flow.

## How it works

The harness directory is read-only from the agent's perspective — never modified at runtime. All project state (workflow templates, env config, built JSON, prompts, JS/Python functions, cloud functions) lives in a separate workspace at `${PWD}/n8n-evol-I-workspace/`, which the agent can `git init` and version-control independently. The workspace layout is opinionated — see below.

The agent reads [`SKILL.md`](SKILL.md) to locate the right sub-skill for any n8n-related request. Each skill is a markdown doc that tells the agent which helper to invoke and with what arguments. Helpers are standalone Python scripts in `helpers/`; there is no master CLI and no daemon.

Code-node logic, prompts, schemas, and HTML templates are stored as separate workspace files and injected at hydration time — the agent never reads or edits megabyte-scale content inlined in workflow JSON. `validate.py` enforces the segmentation discipline before any deploy.

## Workspace layout

`init.py` scaffolds an opinionated workspace tree. Every project that uses n8n-evol-I has the same layout, so the agent never has to ask where a thing should live:

```
n8n-evol-I-workspace/
├── AGENTS.md                # workspace orientation (read first every session)
├── N8N-WORKSPACE-MEMORY.md  # rolling journal — agent appends as it learns
├── n8n-config/              # env YAML (dev.yml, prod.yml, …) + .env.<env> secrets
├── n8n-workflows-template/  # *.template.json — canonical, version-controlled
├── n8n-build/               # hydrated outputs — gitignored, regenerated on deploy
├── n8n-functions/
│   ├── js/                  # pure JS injected via {{@:js:...}}
│   └── py/                  # pure Python injected via {{@:py:...}}
├── n8n-functions-tests/     # *.test.js / test_*.py — paired tests, validator-required
├── n8n-prompts/
│   ├── prompts/             # *_prompt.txt + *_schema.json
│   ├── datasets/            # *.json for iterate-prompt
│   └── evals/
├── n8n-assets/
│   ├── email-templates/     # *.html injected via {{@:html:...}}
│   ├── images/
│   └── misc/
├── cloud-functions/         # FastAPI service scaffolded by add-cloud-function
│   └── functions/
└── cloud-functions-tests/
```

Aliases at the project root (`CLAUDE.md`, `.github/copilot-instructions.md`) point each agent runtime at `AGENTS.md` so the workspace is discoverable from wherever the agent is invoked.

## Repository layout

| Path | Contents |
|---|---|
| [`SKILL.md`](SKILL.md) | Router — lists all lifecycle, pattern, and integration skills. |
| [`install.md`](install.md) | Prerequisites, install, smoke test, update flow. |
| `skills/` | 27 lifecycle + 13 pattern + 10 integration skills (50 total). |
| `helpers/` | 35 top-level Python helpers + 6 `placeholder/` resolvers. |
| `primitives/workflows/` | Seed templates: `_minimal`, `lock_acquisition`, `lock_release`, `error_handler_lock_cleanup`, `rate_limit_check`. |
| `primitives/cloud-functions/` | FastAPI app seed + Railway config (`app.py`, `registry.py`, `railpack.json`). |
| `primitives/prompts/` | Example prompt + schema for `iterate-prompt`. |
| `tests/` | 200+ offline tests (HTTP mocked) covering every helper, primitive, and pattern. |

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for project history.

## License

MIT. See [LICENSE](LICENSE).
