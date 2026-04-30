---
id: debug-failed-execution-yesterday
category: debug
difficulty: hard
---

# Investigate a failed execution from "yesterday"

## Prompt

> "I didn't get my daily report email yesterday. What broke?"

## Expected skills consulted

1. `skills/debug.md`
2. `skills/patterns/investigation-discipline.md`

## Expected helpers invoked

The agent should follow the 8-step investigation rubric in `investigation-discipline.md`. Concretely:

1. Ask user: env? timezone of "yesterday"?
2. `helpers/dependency_graph.py --env <env> --source both` (Step 1: dep graph)
3. `helpers/list_executions.py --env <env> --started-after <ISO-UTC> --tally` (Step 1.5: 7-day baseline + hung counts)
4. `helpers/list_executions.py --env <env> --workflow-key daily_report --started-after <T-1d> --started-before <T> --limit 100` (Step 2: candidate prescreen)
5. `helpers/inspect_execution.py --env <env> --execution-id <id> --include-data` (Step 3: detail)
6. (Step 3b causal-linkage check; Step 5b trigger health if no executions found; Step 6 time-correlation; Step 7 sub-agent cross-check; Step 8 user approval)

## Expected artifacts

None workspace-side. The investigation produces evidence for a recommended fix; the user decides whether to apply it.

## Expected state changes

None — debug flow is read-only by design. Writes (manage_variables, stop_executions, redeploys) only after Step 8 user approval.

## Success criteria

- [ ] Agent identifies the root cause WITH evidence (specific execution id, specific node error).
- [ ] Agent does NOT skip the causal-linkage check — "user says X failed but actually Y didn't produce data" is a real outcome.
- [ ] Agent does NOT recommend a fix until Step 8.

## Pitfalls

- **Existence ≠ causality**. Finding a failed execution doesn't mean it's the right one. Check the time window AND the symptom mapping.
- **Don't stop at the first issue**. A red execution may be downstream of the actual problem (e.g. credential rotation invalidates 5 workflows; the 1st red one gets blamed).
- **Don't guess**. If logs are ambiguous, escalate to the user with a specific question — don't pick the most plausible hypothesis silently.
- For workflows with `n8n-nodes-base.errorTrigger` heads (handlers), the rubric covers indirect-dispatch via `error_source_to_handler` so you can find the SOURCE that failed and triggered the handler.
- "Yesterday" is timezone-relative. Always ask + convert to ISO-UTC before any helper call.
