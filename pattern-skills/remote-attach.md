# Attaching to a foreign n8n instance

## When to use

When you want to point n8n-harness at an n8n instance that isn't already configured in `n8n/environments/<env>.yaml` or root `.env` — for example, a colleague's instance during a pair-debugging session, or a one-off staging instance you don't want to commit to the repo.

## Mechanics

```python
attach("scratch", base_url="https://teammate-instance.app.n8n.cloud", api_key="...")
list_workflows(env="scratch")  # works immediately
deploy("demo_smoke", env="scratch", activate=True)
detach("scratch")
```

`attach()` writes:

- `n8n/environments/attached.<env_name>.yaml` (minimal, with the instance URL)
- `.env.attached.<env_name>` (mode 0600, secrets)

Both are gitignored via globs added in Phase 1a step 8 — they will not be committed by accident.

`detach()` removes both files and clears the cached `N8nClient` for that env. Idempotent.

## Common patterns

- **Triage a teammate's bug:** `attach("teammate", ...)` → `get_workflow("...")` → diff against your local template → patch & `deploy(env="teammate")`.
- **Per-PR review:** `attach("pr-123", ...)` → run the suite sweep against the PR's instance → `detach("pr-123")` once done.
- **Tear down on exit:** consider wrapping in a context manager pattern at the agent level — at the helper level we keep the API simple (call `detach()` yourself).

## Gotchas

- **Don't `attach()` over an existing `<env>.yaml`.** The attach files use the `attached.<name>` prefix; if you pass `env_name="dev"` you'd write `attached.dev.yaml` which is fine — it just sits next to the existing `dev.yaml`. Effective env resolution: env-vars from `.env` → `.env.<env>` → `.env.attached.<env>` (last wins).
- **Validate first.** `attach()` hits `GET /api/v1/workflows` to verify before keeping the files. If validation fails, the files are rolled back. So a bad URL or expired token doesn't leave stale state.
- **Clean up.** `git status` shouldn't show `attached.*.yaml` or `.env.attached.*` files (they're gitignored). If you see them in `git status`, the gitignore glob is wrong — fix `.gitignore` rather than committing them.

## See also

- `pattern-skills/local-instance.md` — for spinning up a Docker-based n8n on your machine.
- `install.md` — for setting up the canonical root `.env` flow (which doesn't need attach).
