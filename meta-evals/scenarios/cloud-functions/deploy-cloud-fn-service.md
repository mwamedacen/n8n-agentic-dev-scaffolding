---
id: deploy-cloud-fn-service
category: cloud-functions
difficulty: medium
---

# Deploy the cloud-functions service to Railway

## Prompt

> "I'm done implementing my two cloud functions. Walk me through deploying them."

## Expected skills consulted

1. `skills/add-cloud-function.md` (the "Deployment" section)

## Expected helpers invoked

None on the harness side — Railway deploy is out of scope. The agent is documentation/guidance for this step, not automation.

## Expected artifacts

None new locally. The agent points the user to:
- Run `railway login` if not authenticated.
- Run `railway link` to associate the project (if first time).
- Run `railway up` from `cloud-functions/`.
- Capture the resulting service URL (e.g. `https://<svc>.railway.app`).
- Optionally add it as an env var in `.env.<env>` so n8n HTTP Request nodes can reference it via `{{@:env:cloudFunctionsBaseUrl}}` (after adding to the env yaml).

## Expected state changes

- Railway project running the FastAPI service.
- (Optional) `<env>.yml` gains `cloudFunctionsBaseUrl: <url>` for placeholder use.

## Success criteria

- [ ] `curl <service-url>/resize_image -d '{...}'` returns a successful response.
- [ ] n8n workflows referencing the cloud-fn URL via `{{@:env:cloudFunctionsBaseUrl}}` resolve cleanly on hydrate.

## Pitfalls

- Railway free-tier services sleep after inactivity. First call after sleep cold-boots in 5-10s — workflows that have low timeouts may timeout. Either bump the workflow's HTTP Request timeout or pay for always-on.
- Don't hardcode the service URL into individual workflow templates — use the env-yaml + `{{@:env:cloudFunctionsBaseUrl}}` pattern so dev / staging / prod can each have their own URL.
- The harness has NO deploy automation for Railway/Supabase — `add_cloud_function.py` only scaffolds. The user runs `railway up` themselves. (If this surprises someone, the docstring on `add-cloud-function.md` says so explicitly.)
