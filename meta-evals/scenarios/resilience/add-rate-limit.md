---
id: add-rate-limit
category: resilience
difficulty: medium
---

# Add a rate-limit gate to a workflow

## Prompt

> "Throttle my `api_v1_handler` workflow at 100 requests per user per minute. When over the limit, return a 4xx-style response so callers know to back off."

## Expected skills consulted

1. `skills/create-lock.md` (with `--include-rate-limit`)
2. `skills/add-rate-limit-to-workflow.md`

## Expected helpers invoked

1. `helpers/create_lock.py --include-rate-limit` (if `rate_limit_check` isn't yet in the workspace)
2. `helpers/add_rate_limit_to_workflow.py --workflow-key api_v1_handler --limit 100 --window-seconds 60 --on-denied passthrough --scope-expression "={{ 'api-v1-' + \$json.userId }}"`
3. `helpers/validate.py --workflow-key api_v1_handler`
4. `helpers/deploy.py --env dev --workflow-key api_v1_handler`

## Expected artifacts

- `rate_limit_check.template.json` in workspace.
- `api_v1_handler.template.json` updated with `Rate Limit` Execute Workflow + `Rate Limit Allowed?` If + denied-branch Set node (passthrough mode).

## Expected state changes

- Workflow deployed + activated. Redis bucket key `n8n-ratelimit-api-v1-<userId>-<bucket>` increments on each call; bucket auto-rolls every 60s.

## Success criteria

- [ ] Within a 60s window, 100 calls succeed and return the normal payload.
- [ ] The 101st call returns `{allowed: false, scope, count, limit}` (passthrough mode).
- [ ] Redis observed: bucket key in the new `n8n-ratelimit-` namespace (post-task-13 rename).

## Pitfalls

- **`--on-denied error` is HTTP-observable as 500** — webhook caller can't distinguish a rate-limit denial from any other workflow error without inspecting `/api/v1/executions`. **`--on-denied passthrough` returns 200 with `{allowed: false, ...}` body** — caller-friendly. **`--on-denied stop` is identical to `error` from the caller's perspective**; the difference is server-side error-handler routing.
- Fixed-window boundary burst: a user can hit `limit=100` near the end of one window and `limit=100` again at the start of the next — up to `2 × limit` across the boundary. If you need strict ceiling-per-rolling-window, this primitive isn't enough; document and consider an external solution.
- Bare-`=` scope-expression is auto-wrapped (with deprecation warning) post-task-12; write canonical `={{ ... }}` form directly to silence the warning.
