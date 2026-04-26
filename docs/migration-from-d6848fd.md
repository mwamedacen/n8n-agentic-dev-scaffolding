# Migration from pre-rebuild (≤ `d6848fd`)

This guide maps the legacy single-repo layout (where the harness checkout WAS the workspace) to the v1.0 skill-package layout (where the harness is a tool and the workspace is separate).

## Old → new mental model

| Old | New |
|---|---|
| `n8n-harness` checkout = your project | `n8n-harness` checkout = read-only skill package |
| `n8n/workflows/*.template.json` | `<workspace>/n8n-workflows-template/*.template.json` |
| `n8n/environments/{dev,prod}.yaml` | `<workspace>/n8n-config/{dev,prod}.yml` |
| `.env`, `.env.dev`, `.env.prod` at repo root | `<workspace>/n8n-config/.env.<env>` |
| `n8n/build_scripts/hydrate_workflow.py` | `helpers/hydrate.py` |
| `n8n/deployment_scripts/deploy_workflow.sh` | `helpers/deploy.py` |
| `n8n/deployment_scripts/deploy_all.sh` | `helpers/deploy_all.py` |
| `n8n/resync_scripts/resync_workflow.sh` | `helpers/resync.py` |
| `n8n/resync_scripts/resync_all.sh` | `helpers/resync_all.py` |
| `n8n/resync_scripts/dehydrate_workflow.py` | `helpers/dehydrate.py` |
| `n8n-harness -c "<python>"` REPL | per-helper CLI invocation |
| `pattern-skills/*.md` | `skills/patterns/*.md` |
| `integration-skills/<service>/*.md` | `skills/integrations/<service>/*.md` |
| `cloud_functions/` (in harness) | `<workspace>/cloud-functions/` (in user project) |
| `common/prompts/`, `common/templates/`, `common/functions/` | `<workspace>/n8n-prompts/`, `<workspace>/n8n-assets/`, `<workspace>/n8n-functions/` |
| `factory/prompt_engineering/` (in harness) | `helpers/iterate_prompt.py` + `<workspace>/n8n-prompts/{datasets,evals}/` |

## Per-command translation

| Old command | New command |
|---|---|
| `cd n8n/deployment_scripts && ./deploy_all.sh dev` | `python3 <harness>/helpers/deploy_all.py --env dev` |
| `cd n8n/deployment_scripts && ./deploy_workflow.sh prod foo` | `python3 <harness>/helpers/deploy.py --env prod --workflow-key foo` |
| `cd n8n/build_scripts && python3 hydrate_all.py -e dev` | (no direct equiv — `deploy.py` and `deploy_all.py` hydrate inline; or loop `hydrate.py --env dev --workflow-key <k>`) |
| `cd n8n/resync_scripts && ./resync_all.sh dev` | `python3 <harness>/helpers/resync_all.py --env dev` |
| `cd n8n/deployment_scripts && ./deactivate_all.sh dev` | `deploy_all.py` auto-deactivates externally-triggered workflows in dev (or call `deactivate.py` per key) |
| `python3 n8n/deployment_scripts/bootstrap_workflows.py dev` | `python3 <harness>/helpers/bootstrap_env.py --env dev` (subsumes both env creation and placeholder minting) |

## Migrating an existing project

1. **Clone the harness** somewhere outside your project:
   ```bash
   cd ~/.claude/skills && git clone https://github.com/<user>/n8n-harness.git
   ```
2. **From your project root**, run `init`:
   ```bash
   cd /path/to/your/project
   python3 ~/.claude/skills/n8n-harness/helpers/init.py
   ```
3. **Move templates** from old `n8n/workflows/*.template.json` to `n8n-harness-workspace/n8n-workflows-template/`.
4. **Move env configs** from old `n8n/environments/{env}.yaml` to `n8n-harness-workspace/n8n-config/{env}.yml`. Update the file extension `.yaml → .yml`.
5. **Move secrets** from old root `.env.<env>` to `n8n-harness-workspace/n8n-config/.env.<env>`.
6. **Move JS / prompts / assets** to their new homes under the workspace (`n8n-functions/`, `n8n-prompts/`, `n8n-assets/`).
7. **Verify** with `python3 <harness>/helpers/doctor.py --env dev` and a small `deploy-run-assert` smoke test.

## What's gone for good

- The `n8n-harness -c "<python>"` evaluator. Skill markdown shows the explicit chain of commands; that's the new ergonomics.
- The `helpers.py` god-file. Each capability lives in a narrow CLI script.
- Auto-update of the harness package. Use `git pull` in the harness checkout — explicit, predictable.
- Local instance lifecycle helpers (`start_local_n8n`, `attach`, etc.). The harness's scope is REST control of an existing instance, not provisioning.

## Pinning the legacy shape

If you need the pre-rebuild commands to keep working in a long-tail script, pin to SHA `d6848fd`. The legacy structure is preserved in git history; the rebuild commit (B-0) wipes it from the working tree.
