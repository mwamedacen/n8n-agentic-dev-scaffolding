---
id: circular-execute-workflow-detected
category: edge-case
difficulty: hard
---

# Circular Execute-Workflow detection

## Prompt

> "I have a chain: `wf_a` → `wf_b` → `wf_c` → `wf_a`. Validate it before deploying."

## Expected skills consulted

1. `skills/debug.md` (mentions dependency_graph)
2. `skills/validate.md`

## Expected helpers invoked

1. `helpers/dependency_graph.py --env dev` (to visualize the graph)
2. (agent inspects the printed adjacency list and detects the cycle by walking it)
3. `helpers/validate.py --workflow-key wf_a --source template` (validator does NOT detect cycles itself; it's a structural validator)

## Expected artifacts

None.

## Expected state changes

None — this is a pre-deploy sanity check.

## Success criteria

- [ ] Agent identifies the cycle by reading dependency_graph output and walking edges manually: `wf_a → wf_b → wf_c → wf_a`.
- [ ] Agent refuses to proceed with deploy until the cycle is broken.
- [ ] Validator's silence on the cycle is acknowledged — it's not a structural issue n8n itself rejects, but it's a runtime infinite loop.

## Pitfalls

- **n8n does NOT reject circular Execute Workflow chains at deploy time** — n8n PUT/activate succeeds. The cycle becomes a runtime infinite loop (each invocation spawns the next; quickly hits worker exhaustion or n8n's max-execution-depth limit, depending on the instance).
- The harness's `dependency_graph.py` is purely informational — it doesn't flag cycles automatically. The agent must walk the adjacency list (or use a topological-sort sketch) to detect.
- For multi-tenant or recursive patterns where re-entry is intentional (rare), the operator overrides this check — no harness mechanism exists to disable it.
- If the cycle is incidental (e.g. `wf_c` was always intended to call `wf_d`, not `wf_a`), fix the template and re-run dependency_graph to confirm.

## Notes

The harness doesn't *prevent* cycles — it gives the agent the tools to *detect* them. This scenario tests the agent's discipline to actually run the check before deploying instead of trusting that "validate clean = safe".
