# meta-evals — agent + harness benchmark suite

> **Invisibility note.** This suite is invisible to the runtime agent. No `SKILL.md` or `skills/**/*.md` references this folder. The scenarios document expected behavior; they are **not** instructions. If you find a cross-reference from `skills/` into here, it's a bug — remove it. The eval's integrity depends on the agent treating the suite as fixtures, not as authoritative guidance.

## What this is

A regression and stress-test matrix for **the agent + the harness combo**. Each scenario captures a natural-language user prompt that an agent equipped with `n8n-evol-I` might receive, plus the expected sequence of skills consulted, helpers invoked, artifacts produced, and observable state changes. Run the suite by handing each prompt to a fresh agent session and grading the result against the per-scenario success criteria.

These are **not** unit tests. They are **not** pytest fixtures. They are user journeys.

## Format

Per-scenario markdown with frontmatter at `meta-evals/scenarios/<category>/<id>.md`. Every file declares:

| Field | Type | Notes |
|---|---|---|
| `id` | kebab-case | unique across the suite |
| `category` | enum | one of: bootstrap, authoring, resilience, cloud-functions, multi-env, deploy, resync, debug, lifecycle, prompt-iteration, edge-case |
| `difficulty` | enum | trivial, easy, medium, hard, expert |
| `prompt` (body section) | text | verbatim conversational input the user might give |
| `expected_skills_consulted` | list, ordered | which `skills/*.md` the agent should read, in order |
| `expected_helpers_invoked` | list, ordered | which `helpers/*.py` the agent should run, with key flags |
| `expected_artifacts` | list | files created or modified in the workspace |
| `expected_state_changes` | list | what should change on the n8n instance / Redis |
| `success_criteria` | bulleted | offline + live verification checks |
| `pitfalls` | bulleted | known traps the agent should avoid |
| `notes` | text | optional commentary on harness behavior |

## Coverage

42 scenarios across 11 categories:

| Category | # | Why it matters |
|---|---|---|
| `bootstrap` | 4 | First-touch UX; init + env config + credentials + variables |
| `authoring` | 7 | Workflow-shape coverage — webhook, cron, form, sub-workflow, JS / Python / static-asset placeholders |
| `resilience` | 5 | Locks, rate-limits, error handlers, combos |
| `cloud-functions` | 3 | FastAPI scaffold (the post-Pyodide-removal escape hatch on n8n Cloud) |
| `multi-env` | 3 | Promotion, resync, rollback |
| `deploy` | 5 | Single, tier-ordered, strict-activate, Cloud publish caveat, deploy-run-assert |
| `resync` | 3 | Single + all + UI-edit drift |
| `debug` | 4 | Failed-execution investigation, tally, dependency graph, doctor verdict routing |
| `lifecycle` | 3 | Archive, unarchive, deactivate |
| `prompt-iteration` | 1 | DSPy optimization |
| `edge-case` | 4 | Adversarial / negative paths the agent must handle gracefully |
| **total** | **42** | |

## How to run

This suite has no built-in execution engine. Run scenarios by:

1. Pick a scenario file.
2. Open a fresh agent session with the harness installed (or visible via `${CLAUDE_PLUGIN_ROOT}`).
3. Paste the scenario's `Prompt` section verbatim.
4. Let the agent work.
5. Grade against `Success criteria` and check `Pitfalls` weren't tripped.
6. Record pass/fail/partial in your evaluator's tracking system.

Optional: `runner.py` (~40 lines) prints a checklist scaffold for human/agent operators iterating through the suite. It does not execute the scenarios.

## Pitfalls captured (post-fix behavior)

The `pitfalls` sections describe how the harness *currently* behaves after the task #9 / #12 / #13 deep-dive fixes:

- **Bare-`=` scope-expression** auto-wraps to canonical `={{ ... }}` form with a deprecation warning. Agent should still write canonical form directly.
- **Cloud-functions `conftest.py`** is auto-seeded by `init.py`. No manual setup required.
- **Sentinel placeholder ids** (`'placeholder'`, `''`, `'your-...'`) trigger `ValueError` at hydrate-time when referenced via `{{@:env:workflows.X.id}}`. Run `bootstrap-env` to mint real IDs.
- **n8n Cloud sub-workflow activation** requires the callee to be activated first (n8n's "publish" terminology — but the API path is `/activate`, not `/publish`). Use `deploy_all.py` tier ordering.
- **`{{@:py:...}}` Python Code nodes** post-Pyodide-removal have reduced capability on n8n Cloud (no binary handling, no arbitrary deps). Defer to cloud-function scaffold for those needs.
- **Ownership-checked release** raises `LOGIC ERROR: Lock held by ...` if the caller passes a `lock_id` that doesn't match the stored owner. Catches caller bugs.
- **`lockScopes` env config** must list every static lock scope for active error-handler cleanup to find them. `add_lock_to_workflow.py` auto-registers static literals; dynamic scopes need manual entries.

## Philosophy

The agent is the system under test, not just the harness. A scenario passes only if the agent picks the right skill, runs the right helper with the right flags, produces the right artifacts, AND avoids the documented pitfalls. A green offline test suite + a successful live deploy don't matter if the agent took a circuitous path or muddied the workspace along the way.

Scenarios document the *expected* journey. Deviations are signal — investigate before declaring a fail.
