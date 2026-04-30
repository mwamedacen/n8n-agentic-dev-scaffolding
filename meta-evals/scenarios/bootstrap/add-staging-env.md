---
id: add-staging-env
category: bootstrap
difficulty: easy
---

# Add a second environment (staging) to an existing project

## Prompt

> "I've been working in dev. Set up a staging env that points at our n8n staging instance — `staging.n8n.example.com`. Use a different display name and workflow postfix so I can tell them apart."

## Expected skills consulted (in order)

1. `skills/bootstrap-env.md`

## Expected helpers invoked

1. `helpers/bootstrap_env.py --env staging --instance staging.n8n.example.com --display-name Staging --postfix " [STAGING]"`

## Expected artifacts

- `n8n-config/staging.yml` with `name: staging`, `displayName: Staging`, `workflowNamePostfix: " [STAGING]"`, `n8n.instanceName: staging.n8n.example.com`, empty `credentials: {}`, empty `workflows: {}`.
- `n8n-config/.env.staging` (mode 0600) — agent should prompt the user for their `N8N_API_KEY` and write it.

## Expected state changes

- Validation `GET /workflows?limit=1` against `staging.n8n.example.com`. If 401, the helper rolls back any stage-1 writes and exits 1.
- If existing workflows in YAML have placeholder ids, helper mints real ones via `POST /workflows`. Fresh env starts empty so this is a no-op for stage 3.

## Success criteria

- [ ] `staging.yml` parses cleanly via `doctor.py --env staging`.
- [ ] `.env.staging` has restrictive permissions (0600).
- [ ] `doctor.py --env staging --json` returns `verdict: "ok"` (or `needs-mint` if workflows are added later).

## Pitfalls

- Helper rolls back YAML on stage-2 validation failure. If you see `Rolled back any files written in this run`, the API key or instance URL is wrong — fix and retry; don't manually create the YAML.
- Don't reuse the dev API key for staging unless the same n8n project covers both — separate instances need separate JWTs.

## Notes

The staging env shares `n8n-workflows-template/` with dev — there's no per-env template directory. Per-env divergence comes from the YAML's `workflows.<key>.id` values (each env mints its own placeholder id).
