# n8n-harness

A skill package for driving n8n from code. Designed to be read by a coding agent.

## Why

n8n is a capable workflow automation platform, but operating it at scale from code requires the same boilerplate on every project: REST-API wrappers, per-environment config management, a way to keep workflow logic in version control, and enough structural discipline that a coding agent can author and deploy without re-learning the API surface every session.

n8n-harness provides that structure. It is a read-only skill package: the agent reads markdown sub-skills from `skills/` and invokes Python helpers from `helpers/` against a separate per-project workspace. Workflow templates live in the workspace, not in the harness, so the harness can be updated with `git pull` without touching user content. The agent needs to know only one thing: read `SKILL.md` first.

## Features

- **Multi-environment workflows.** Configure dev, staging, and prod in `n8n-config/<env>.yml` with per-env instance URLs, workflow IDs, and credential refs. Every helper accepts `--env`. See [`bootstrap-env.md`](skills/bootstrap-env.md).

- **Build-time substitution keeps heavy resources out of workflow JSON.** Code, prompts, schemas, email templates, env values, and UUIDs live in dedicated workspace files (`n8n-functions/`, `n8n-prompts/`, `n8n-assets/`, `n8n-config/`). Templates reference them via `{{HYDRATE:js|py|txt|json|html|env|uuid:...}}` placeholders that `hydrate.py` substitutes at deploy time; `dehydrate.py` re-extracts on resync, so round-trips with the n8n UI are byte-stable. The agent edits a 50-line `*.template.json` plus separate code/prompt/template files instead of a 200KB blob with everything inlined.

  ```jsonc
  // n8n-workflows-template/aggregate.template.json
  { "type": "n8n-nodes-base.code",
    "parameters": { "jsCode": "{{HYDRATE:js:n8n-functions/js/aggregate.js}}\n\nreturn aggregate(items);" } }
  ```

  See [`skills/patterns/code-node-discipline.md`](skills/patterns/code-node-discipline.md) for the strict-mode rule on JS/Python segmentation.

- **Dependency-ordered deployment.** `deploy_all.py` rolls out an entire env in tier order so callee sub-workflows deploy before callers. Tier assignment is set per-workflow at create time via `n8n-config/deployment_order.yml`. See [`deploy-all-workflows-in-env.md`](skills/deploy-all-workflows-in-env.md).

- **Execution debugging.** `inspect-execution.md` guides a structured investigation from symptom to root cause: dependency-graph traversal, candidate pre-screening, per-execution causal-linkage checks, trigger health, blast-radius enumeration, and a prescribed sub-agent cross-check step. Backed by `list_executions.py`, `inspect_execution.py`, and `dependency_graph.py`. See [`skills/patterns/investigation-discipline.md`](skills/patterns/investigation-discipline.md).

- **Distributed locking.** Redis-backed acquire/release primitives (`lock_acquisition`, `lock_release`) with owner-pointer tracking so a crash lets the next caller identify and clean up a held scope. Locks self-heal via Redis TTL if the error handler is not configured. `add-lock-to-workflow.md` wraps any workflow in lock/release in one command. See [`skills/patterns/locking.md`](skills/patterns/locking.md).

- **Rate limiting.** Fixed-window Redis INCR primitive (`rate_limit_check`) with configurable limit, window, and denied-branch behavior (passthrough / stop / error). `add-rate-limit-to-workflow.md` gates any workflow at the head of its main flow. See [`skills/patterns/locking.md`](skills/patterns/locking.md).

- **Cloud function scaffolding.** `add-cloud-function.md` scaffolds a Python function into a FastAPI service in `cloud-functions/` and auto-registers it in the app's router. The service ships with Railway deployment config (`railpack.json`); callable from n8n via HTTP Request nodes. See [`skills/add-cloud-function.md`](skills/add-cloud-function.md).

- **Prompt optimization with DSPy.** `iterate-prompt.md` runs BootstrapFewShot or MIPROv2 against a workspace prompt + schema + dataset, evaluates on structural correctness, and optionally exports the optimized prompt back to disk. Requires `pip install dspy litellm`. See [`skills/iterate-prompt.md`](skills/iterate-prompt.md).

## Quick start

```bash
# One-time: clone into your agent's skills directory
git clone https://github.com/mwamedacen/n8n-harness.git ~/.claude/skills/n8n-harness
pip install pyyaml requests python-dotenv

# Per project
python3 ~/.claude/skills/n8n-harness/helpers/init.py
python3 ~/.claude/skills/n8n-harness/helpers/bootstrap_env.py \
  --env dev --instance acme.app.n8n.cloud --api-key <key>
python3 ~/.claude/skills/n8n-harness/helpers/doctor.py --env dev
```

See [`install.md`](install.md) for full prerequisites, optional extras, and update flow.

## How it works

The harness directory is read-only from the agent's perspective — never modified at runtime. All project state (workflow templates, env config, built JSON, prompts, JS/Python functions, cloud functions) lives in a separate workspace at `${PWD}/n8n-harness-workspace/`, which the agent can `git init` and version-control independently. The workspace layout is opinionated — see below.

The agent reads [`SKILL.md`](SKILL.md) to locate the right sub-skill for any n8n-related request. Each skill is a markdown doc that tells the agent which helper to invoke and with what arguments. Helpers are standalone Python scripts in `helpers/`; there is no master CLI and no daemon.

Code-node logic, prompts, schemas, and HTML templates are stored as separate workspace files and injected at hydration time — the agent never reads or edits megabyte-scale content inlined in workflow JSON. `validate.py` enforces the segmentation discipline before any deploy.

## Workspace layout

`init.py` scaffolds an opinionated workspace tree. Every project that uses n8n-harness has the same layout, so the agent never has to ask where a thing should live:

```
n8n-harness-workspace/
├── AGENTS.md                # workspace orientation (read first every session)
├── N8N-WORKSPACE-MEMORY.md  # rolling journal — agent appends as it learns
├── n8n-config/              # env YAML (dev.yml, prod.yml, …) + .env.<env> secrets
├── n8n-workflows-template/  # *.template.json — canonical, version-controlled
├── n8n-build/               # hydrated outputs — gitignored, regenerated on deploy
├── n8n-functions/
│   ├── js/                  # pure JS injected via {{HYDRATE:js:...}}
│   └── py/                  # pure Python injected via {{HYDRATE:py:...}}
├── n8n-functions-tests/     # *.test.js / test_*.py — paired tests, validator-required
├── n8n-prompts/
│   ├── prompts/             # *_prompt.txt + *_schema.json
│   ├── datasets/            # *.json for iterate-prompt
│   └── evals/
├── n8n-assets/
│   ├── email-templates/     # *.html injected via {{HYDRATE:html:...}}
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
| `skills/` | 25 lifecycle + 13 pattern + 10 integration skills (48 total). |
| `helpers/` | 35 top-level Python helpers + 6 `placeholder/` resolvers. |
| `primitives/workflows/` | Seed templates: `_minimal`, `lock_acquisition`, `lock_release`, `error_handler_lock_cleanup`, `rate_limit_check`. |
| `primitives/cloud-functions/` | FastAPI app seed + Railway config (`app.py`, `registry.py`, `railpack.json`). |
| `primitives/prompts/` | Example prompt + schema for `iterate-prompt`. |
| `tests/` | Offline tests (HTTP mocked) for each helper. |

## License

MIT. See [LICENSE](LICENSE).
