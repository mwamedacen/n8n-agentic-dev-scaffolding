---
id: list-executions-7day-tally
category: debug
difficulty: easy
---

# 7-day execution tally for an env

## Prompt

> "Give me a quick sanity check: how many executions ran on dev this week, by status?"

## Expected skills consulted

1. `skills/debug.md` (mentions `list_executions.py --tally` in step 1.5)

## Expected helpers invoked

1. `helpers/list_executions.py --env dev --started-after <ISO-1week-ago> --tally`

## Expected artifacts

None.

## Expected state changes

None.

## Success criteria

- [ ] Helper outputs a JSON object with `count`, `by_status` (success/error/running/canceled/waiting/crashed/queued), `hung_count`, `crash_count`, `running_hung_count`.
- [ ] Agent surfaces anomalies: high error rate? Hung executions still in `running` past their expected duration?

## Pitfalls

- **Hung executions** (status `running` for hours) are often more revealing than failed ones. A workflow stuck in `running` consumes worker capacity — `stop_executions.py` cancels them, but only after Step 8 user approval per investigation discipline.
- The tally doesn't paginate cleanly across very-large windows — n8n's `/executions` endpoint caps at 250 per page. The helper handles pagination but for >10k executions consider narrowing the window or filtering by workflow-key.
- Be careful comparing tallies across days: weekend dips, business-hours peaks, etc. don't always indicate a problem.
