---
id: init-fresh-project
category: bootstrap
difficulty: trivial
---

# Initialize a fresh n8n-evol-I project

## Prompt

> "I want to start managing my n8n workflows in code. Set up the project."

## Expected skills consulted (in order)

1. `SKILL.md` — to see the lifecycle table.
2. `skills/init.md` — for the workspace-scaffold flow.
3. `skills/bootstrap-env.md` — for the next-step env config.

## Expected helpers invoked

1. `helpers/init.py` — scaffolds `<cwd>/n8n-evol-I-workspace/`.

## Expected artifacts

- `n8n-evol-I-workspace/` directory tree:
  - `n8n-config/` (with `.env.example`)
  - `n8n-workflows-template/`
  - `n8n-build/`
  - `n8n-prompts/{prompts,datasets,evals}/`
  - `n8n-functions/{js,py}/`
  - `n8n-functions-tests/conftest.py`
  - `cloud-functions/{,functions/}` + `cloud-functions-tests/conftest.py`
  - `n8n-assets/{email-templates,images,misc}/`
  - `AGENTS.md`, `N8N-WORKSPACE-MEMORY.md`, `.gitignore`
- If `pwd` matches the parent of the new workspace: `CLAUDE.md` and `.github/copilot-instructions.md` aliases at project root.

## Expected state changes

None on the n8n instance — `init.py` is purely local filesystem.

## Success criteria

- [ ] `n8n-evol-I-workspace/` exists with all subdirs above.
- [ ] `cloud-functions-tests/conftest.py` exists and adds `cloud-functions/` to `sys.path`.
- [ ] `pytest cloud-functions-tests/` runs cleanly out of the box (after a later `add_cloud_function`).
- [ ] Agent points the user to `bootstrap-env` as the next step.

## Pitfalls

- Don't use `--force` unless explicitly asked — it clobbers an existing workspace.
- If the user's `pwd` is non-default, the alias-file step is silently skipped (init prints a NOTE). Agent should mention this.
