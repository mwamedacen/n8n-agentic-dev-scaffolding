---
id: expired-jwt-graceful
category: edge-case
difficulty: easy
---

# Expired JWT — graceful failure path

## Prompt

> "Deploy `daily_report` to dev. (User's API key in `.env.dev` expired yesterday.)"

## Expected skills consulted

1. `skills/doctor.md` (the agent's first move on any unexpected 401)
2. `skills/bootstrap-env.md`

## Expected helpers invoked

1. `helpers/deploy.py --env dev --workflow-key daily_report` → 401 raised
2. (agent immediately runs) `helpers/doctor.py --env dev --json` → verdict `api-unreachable`
3. (agent surfaces the actionable error to the user)

## Expected artifacts

None new.

## Expected state changes

None — the deploy fails before any PUT.

## Success criteria

- [ ] Agent sees the 401, runs doctor, recognizes verdict `api-unreachable`, and tells the user clearly: "Your N8N_API_KEY in `.env.dev` is rejected. Refresh the JWT in n8n's UI (Settings → API → New API key) and update `.env.dev`."
- [ ] Agent does NOT retry the deploy in a loop hoping for a different result.
- [ ] Agent does NOT fabricate a workaround like "let's try the MCP archive endpoint instead" — that's not the issue.

## Pitfalls

- 401 from `requests.raise_for_status()` produces a noisy traceback. The agent's job is to translate that into the actionable user message — not just paste the traceback.
- If the JWT is expired, ALL `helpers/*` that hit the n8n API will fail the same way. Don't try `bootstrap_env.py` "just in case" — same 401.
- The harness has no auto-refresh — n8n cloud doesn't expose a token-refresh endpoint to the public API. User must log in and mint a new one manually.

## Notes

The doctor verdict `api-unreachable` is the canonical signal. The agent should treat it as a hard stop pending user action.
