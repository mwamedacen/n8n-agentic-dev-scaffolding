# meta-evals/runner — eval orchestration & grading

> **Invisibility note (same rule as the rest of `meta-evals/`).**
> No file under `skills/`, `SKILL.md`, `install.md`, or top-level `README.md`
> references this folder. The runner is observable from outside but invisible
> to the agent under test.

## What this is

A six-file scaffold that drives a coding agent (default: Claude Code) through
the 42 scenarios in `meta-evals/scenarios/`, captures each sub-agent's behavior,
grades against the scenario's hidden rubric, cleans up live n8n state, and
aggregates a graded report + replay instructions.

## Files

| File | Role |
|---|---|
| `orchestrate.md` | Long-form instruction for the orchestrator (a Claude Code session). Loops scenarios, spawns sub-agents via the `Agent` tool, grades, cleans up. |
| `sub_agent_prompt.md` | Template wrapping each scenario's `## Prompt` for the sub-agent. Carries hard rules (don't peek at meta-evals/, no commits) + a per-scenario "self-bootstrap your prerequisites" rider for the 3 hard scenarios. |
| `state.py` | Snapshots n8n state (workflows + recent executions + variables) before/after each scenario; emits set-difference JSON for the grader. |
| `grade.py` | Parses scenario rubric (Success criteria, Pitfalls, Expected helpers). Walks each criterion: rule-based eval where possible, marks `requires_judge: true` for behavioral ones. Outputs `grade.json` with three tiers (outcome, path, pitfalls) + weighted rollup + letter grade. |
| `cleanup.py` | Deactivates + archives every workflow on the n8n instance whose name carries the run's `EVAL_PREFIX`. Deletes prefix-tagged variables. Redis lock/rate-limit keys self-clean via short TTL. |
| `report.py` | Aggregates per-scenario `grade.json` files into `summary.md` (graded report) + `replay.md` (cross-agent reproduction instructions). |

## How to invoke

In a Claude Code session opened at the repo root:

> Read `meta-evals/runner/orchestrate.md` and execute it. Use `.env.bak.dod` as
> the credential source. RUN_ID = <fresh-timestamp>.

That's the entire user-facing surface. The orchestrator (Claude Code itself)
takes it from there.

## Per-tool details

**`state.py`** — two subcommands:

```bash
python3 meta-evals/runner/state.py snapshot \
    --env dev --workspace <ws> --output <ws>/.eval/before.json

python3 meta-evals/runner/state.py diff \
    --before before.json --after after.json --output diff.json
```

**`grade.py`** — one subcommand `grade`. Reads the scenario MD by id, walks
its `## Success criteria` bullets, classifies each (filesystem / regex /
state-shaped / helper-invoke / behavioral), evaluates rule-based ones,
defers behavioral ones to the orchestrator. Output structure documented at
the top of `grade.py`.

**`cleanup.py`** — one subcommand `cleanup`. Lists workflows + variables on
the live instance, filters by `--eval-prefix` substring, archives + deletes.
Idempotent. Safe to re-run.

**`report.py`** — one subcommand `aggregate`. Builds the human-readable
summary + replay docs. Optionally `--baseline <prior-run-id>` to add a delta
column.

## Output layout

```
meta-evals/results/<run-id>/
├── summary.md                 # graded report, per-scenario table + aggregates
├── replay.md                  # cross-agent reproduction instructions
└── <scenario-id>/
    ├── prompt_sent.txt        # the templated prompt the sub-agent received
    ├── transcript.txt         # sub-agent's full text response
    ├── before.json            # pre-scenario n8n state snapshot
    ├── after.json             # post-scenario n8n state snapshot
    ├── after_cleanup.json     # post-cleanup confirmation snapshot
    ├── grade.json             # per-criterion + rollup grade
    └── cleanup.json           # cleanup report (what was archived/deleted)
```

The whole `results/` directory is gitignored (see `meta-evals/.gitignore`).

## Grading model

Three tiers, weighted rollup:

- **Outcome (70%)** — rule-based pass/fail per `## Success criteria` bullet.
  Filesystem checks, helper-invocation checks, n8n-state-diff checks.
  Behavioral criteria are deferred to the orchestrator-as-judge.
- **Path (20%)** — overlap between `## Expected helpers invoked` and what the
  sub-agent actually ran (extracted from transcript + self-report).
- **Pitfalls (10%)** — `1 - n_hit / n_documented`. Detects common failure
  modes (used `--force` unnecessarily, ran `git commit`, used bare-`=` scope,
  etc.) by transcript greps.

Letter grade: A ≥85, B ≥70, C ≥55, D ≥40, F <40.

## Anti-gaming

The sub-agent receives **only** the scenario's `## Prompt` body, never the
rubric. The runner enforces this by templating the sub-agent prompt from
`sub_agent_prompt.md` and rejecting any inclusion of `## Success criteria`
or `## Pitfalls` content.

After the run, the orchestrator runs:

```bash
grep -l "meta-evals" meta-evals/results/<run-id>/*/transcript.txt
```

Any matches signal a leak — fix the prompt template before trusting the
results.

## Bias disclosure

The orchestrator (Claude Code) grading the sub-agent (also Claude Code) carries
self-preference bias. We mitigate by keeping outcome (the dominant tier) fully
rule-based; orchestrator-as-judge only applies to the path + behavioral
slivers (≤30% of rollup weight).
