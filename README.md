# n8n-harness

A read-only **skill package** for authoring, deploying, and operating n8n workflows from code — designed to be driven by a coding agent.

The package contains markdown sub-skills (the agent's instruction surface), Python helper scripts (the executable surface), and seed primitives (lock workflows, a FastAPI cloud-function app, prompt + schema scaffolds). It does **not** contain user project state — that lives in a separate workspace at `${PWD}/n8n-harness-workspace/`.

## What's distinctive

- **Read-only skill / writeable workspace separation.** The harness directory is never modified at runtime. All authored artifacts (templates, env config, JS/Python code, prompts, cloud functions) land in `${PWD}/n8n-harness-workspace/`. Updates are `git pull` on the harness; user content is unaffected.
- **Code-node discipline, enforced.** Logic inside an n8n Code node must be a pure function extracted to `n8n-functions/{js,py}/<name>.{js,py}` and injected via `{{HYDRATE:js|py:...}}`. A paired test under `n8n-functions-tests/` is required. `validate.py` hard-fails inlined Code-node bodies and rejects the deprecated `n8n-nodes-base.function` node type entirely. `deploy.py` runs validation automatically before pushing. See [`skills/patterns/code-node-discipline.md`](skills/patterns/code-node-discipline.md).
- **Round-trippable templates.** `dehydrate` collapses live n8n exports back to placeholder-bearing templates so manual edits in the n8n UI don't leak duplicated function bodies or stale env values into version control.
- **No master CLI.** Each helper under `helpers/` is independently invokable by absolute path. There is no console script and no PATH pollution.
- **Pure REST + per-env config.** Every helper talks to n8n over the official REST API using `pyyaml` + `requests` + `python-dotenv`. No browser automation, no SDK lock-in.

## Install

Clone into your agent's skills directory:

```bash
cd ~/.claude/skills   # or wherever your agent runtime reads skills from
git clone https://github.com/mwamedacen/n8n-scaffolder-for-coding-agents.git n8n-harness
```

Install Python deps (lightweight by default):

```bash
pip install pyyaml requests python-dotenv
# Optional, only for `iterate-prompt`:
pip install dspy litellm
```

See [`install.md`](install.md) for prerequisites, smoke test, and update instructions.

## Usage

The agent reads [`SKILL.md`](SKILL.md) first — it's the router that maps any n8n-related request onto the right sub-skill.

A typical first session:

```bash
cd /path/to/your/project
python3 ~/.claude/skills/n8n-harness/helpers/init.py
python3 ~/.claude/skills/n8n-harness/helpers/bootstrap_env.py \
  --env dev --instance acme.app.n8n.cloud --api-key <your-key>
python3 ~/.claude/skills/n8n-harness/helpers/doctor.py --env dev
```

After that, the agent authors workflows via `create-new-workflow.md`, deploys via `deploy-single-workflow-in-env.md`, runs end-to-end via `deploy-run-assert.md`, and so on.

## Mental model

- The harness directory is **read-only** from the agent's perspective.
- The workspace at `${PWD}/n8n-harness-workspace/` holds all authored artifacts.
- Helpers under `helpers/<name>.py` are invoked by absolute path; there is no master CLI.
- Skills under `skills/` are markdown docs telling the agent what to do and which helper to invoke. Patterns and integrations are reference docs read while authoring.

## Repository layout

| Path | Contents |
|---|---|
| [`SKILL.md`](SKILL.md) | Router — first thing the agent reads. Lists the lifecycle, pattern, and integration skills. |
| [`install.md`](install.md) | Prerequisites, install, smoke test, update flow. |
| [`CHANGELOG.md`](CHANGELOG.md) | Version history. |
| `skills/` | 22 lifecycle skills + 11 [`patterns/`](skills/patterns) + 8 [`integrations/`](skills/integrations) (41 markdowns total). |
| `helpers/` | 28 top-level Python helpers (init, bootstrap_env, hydrate, deploy, run, resync, validate, …) plus 6 [`placeholder/`](helpers/placeholder) resolvers (env, file, js, py, uuid, validator). |
| `primitives/workflows/` | Seed templates copied into the workspace on demand: `_minimal`, `lock_acquisition`, `lock_release`, `error_handler_lock_cleanup`. |
| `primitives/cloud-functions/` | Deployable FastAPI app seed: `app.py`, `registry.py`, `functions/`, `requirements.txt`, `railpack.json`, `railway.toml`. |
| `primitives/prompts/` | Example prompt + schema pair for `iterate-prompt`. |
| `tests/` | Offline tests for each helper (HTTP mocked). |
| `docs/` | [`migration-from-d6848fd.md`](docs/migration-from-d6848fd.md) — pre-rebuild → current path/command mapping. |

For the full skill catalogue (lifecycle, patterns, integrations) see [`SKILL.md`](SKILL.md).

## License

MIT. See [`LICENSE`](LICENSE).
