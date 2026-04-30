---
id: doctor-json-verdict-routing
category: debug
difficulty: easy
---

# Use doctor `--json` verdict to route the next agent action

## Prompt

> "Run a health check and tell me the next step automatically."

## Expected skills consulted

1. `skills/doctor.md`

## Expected helpers invoked

1. `helpers/doctor.py --workspace <ws> --env dev --json`

## Expected artifacts

None — JSON is printed to stdout.

## Expected state changes

None.

## Success criteria

- [ ] Agent parses `verdict` and routes:
  - `ok` → no action; tell the user "all green".
  - `needs-bootstrap` → run `bootstrap_env.py --env dev`.
  - `needs-mint` → run `bootstrap_env.py --env dev` (mints placeholder ids).
  - `api-unreachable` → check `.env.dev` API key, network, instance URL.
  - `audit-findings` → user-decision; report which categories.
  - `lock-scopes-unregistered` → add the static lock scope strings to `<env>.yml.lockScopes` (or use `add_lock_to_workflow.py` which auto-registers).
  - `fail` → some other failure row; show `checks[]` to user.

## Pitfalls

- **Stable verdict enum** (post-task-9 + post-task-13). The set is: `ok | needs-bootstrap | needs-mint | api-unreachable | audit-findings | lock-scopes-unregistered | fail`. Any other value is a bug.
- The `checks` list is a per-row breakdown (state ∈ {ok, warn, fail}, label, detail). Use it for human-readable display; use `verdict` for routing.
- `--with-audit` is OFF by default (audit can be slow on large instances). Pass `--with-audit` when you want a deeper read; expect 2-30s extra latency.
