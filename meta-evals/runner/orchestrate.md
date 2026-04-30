# Orchestrator instructions for running the meta-evals suite

Read this file when a human asks you (Claude Code, a session opened in the
`n8n-evol-I/` repo) to drive an eval run. You are the **orchestrator**. You
spawn one sub-agent per scenario via the `Agent` tool, capture each one's
output, grade it against the scenario's hidden rubric, run cleanup, and
aggregate to a final report.

## Pre-flight

Before launching any scenarios, verify:

1. The harness is at the directory you're in (`pwd` should be the repo root).
2. `.env.bak.dod` exists at `<repo-root>/.env.bak.dod` (or wherever the human
   tells you). It must contain `N8N_API_KEY` and `N8N_INSTANCE_NAME`.
3. The n8n instance is reachable: temporarily stage `.env.bak.dod` into a
   throwaway workspace and run `helpers/doctor.py --json --env dev` — verdict
   should be `ok` or `needs-mint`. If `api-unreachable`, refuse to start and
   tell the human to refresh the JWT.
4. Pick a `RUN_ID = "$(date +%s)"`. All artifacts go under
   `meta-evals/results/<RUN_ID>/`.
5. Pick an `EVAL_PREFIX = "evolI-eval-<RUN_ID>"`. Sub-agents use this to tag
   anything they create on the n8n instance, and the cleanup step uses it to
   find what to remove.

## Scenario-execution loop

For each scenario file under `meta-evals/scenarios/<category>/<id>.md`,
in this order (offline first, then live-readonly, then live-write — see
`# Execution order` below):

### Step 1 — Read the scenario file

Parse:
- `id` (frontmatter)
- `category` (frontmatter)
- `difficulty` (frontmatter)
- `## Prompt` body — verbatim text the user would say
- `## Success criteria` — what passing looks like (HIDDEN from sub-agent)
- `## Pitfalls` — failure modes the agent should avoid (HIDDEN from sub-agent)
- `## Expected skills consulted` — for path-discipline grading (HIDDEN)
- `## Expected helpers invoked` — for path-discipline grading (HIDDEN)

### Step 2 — Provision a fresh sandboxed workspace

```bash
WORKSPACE="/tmp/eval-${RUN_ID}/${SCENARIO_ID}"
mkdir -p "$WORKSPACE"
python3 helpers/init.py --workspace "$WORKSPACE"
mkdir -p "$WORKSPACE/n8n-config"
cp <repo-root>/.env.bak.dod "$WORKSPACE/n8n-config/.env.dev"
chmod 600 "$WORKSPACE/n8n-config/.env.dev"
mkdir -p "$WORKSPACE/.eval"
```

For scenarios in execution-class `live-write` or `live-readonly`, also bootstrap
the env so the agent has a usable `<env>.yml`:

```bash
python3 helpers/bootstrap_env.py --workspace "$WORKSPACE" --env dev \
  --instance "$N8N_INSTANCE_NAME"  # read from .env.bak.dod
```

(Skip for pure-offline scenarios — those don't touch the YAML.)

### Step 3 — Pre-snapshot live state

For live-readonly + live-write scenarios:

```bash
python3 meta-evals/runner/state.py snapshot --env dev \
  --workspace "$WORKSPACE" --output "$WORKSPACE/.eval/before.json"
```

### Step 4 — Build the sub-agent prompt

Read `meta-evals/runner/sub_agent_prompt.md`. Substitute:

- `{HARNESS_ROOT}` → absolute path to the n8n-evol-I directory
- `{WORKSPACE}` → `$WORKSPACE`
- `{NOW_UTC}` → current ISO timestamp
- `{EVAL_PREFIX}` → `$EVAL_PREFIX`
- `{PROMPT_VERBATIM}` → the scenario's `## Prompt` body (EVERYTHING ELSE
  from the scenario file is hidden from the sub-agent)
- `{SCENARIO_RIDER}` → see "Hard-scenario riders" table below; empty for
  most scenarios

### Step 5 — Spawn the sub-agent

Use the `Agent` tool with `subagent_type: "general-purpose"`:

```python
Agent(
    description=f"Eval scenario: {SCENARIO_ID}",
    subagent_type="general-purpose",
    prompt=<the templated prompt from Step 4>,
)
```

Capture the sub-agent's full text response. Save to
`$WORKSPACE/.eval/transcript.txt`. Set a 15-minute soft timeout per scenario;
hard timeout 30 min (orchestrator decides; the Agent tool itself doesn't
enforce one).

### Step 6 — Post-snapshot live state

Same as Step 3 but writing to `$WORKSPACE/.eval/after.json`.

### Step 7 — Grade

```bash
python3 meta-evals/runner/grade.py grade \
  --scenario-id "$SCENARIO_ID" \
  --scenarios-dir meta-evals/scenarios \
  --workspace "$WORKSPACE" \
  --transcript "$WORKSPACE/.eval/transcript.txt" \
  --before "$WORKSPACE/.eval/before.json" \
  --after "$WORKSPACE/.eval/after.json" \
  --eval-prefix "$EVAL_PREFIX" \
  --output "$WORKSPACE/.eval/grade.json"
```

The grader does:
- **Outcome tier** (rule-based, deterministic): walk each `## Success criteria`
  bullet, classify it (filesystem check / regex / state-diff / behavioral),
  evaluate the rule-based ones directly. Behavioral criteria get marked
  `requires_judge: true` in the output.
- **Path tier** (string-overlap): extract shell commands from transcript,
  match against `## Expected helpers invoked`, compute overlap.
- **Pitfall tier**: grep transcript for documented failure patterns.

### Step 8 — Apply orchestrator-as-judge for behavioral criteria

For each `requires_judge: true` criterion in `grade.json`, read the transcript
and apply your own judgment. Examples of behavioral criteria:

- "Agent points the user to bootstrap-env as the next step."
- "Agent does NOT recommend a fix until Step 8 (debug rubric)."
- "Agent surfaces anomalies: high error rate? Hung executions?"

For each, scan the transcript and decide pass/fail. Update `grade.json` in
place — set the criterion's `pass: true|false` and add a one-sentence
rationale to the criterion's `notes` field.

You're being asked to grade Claude Code with Claude Code — there's
self-preference bias here. Mitigate by being extra strict on behavioral
criteria; if the transcript is ambiguous, default to fail. Document the bias
in the run's `summary.md` so consumers know.

### Step 9 — Cleanup live state

For live-write scenarios, run the cleanup script. Pure-offline scenarios skip
this step.

```bash
python3 meta-evals/runner/cleanup.py cleanup \
  --env dev \
  --workspace "$WORKSPACE" \
  --eval-prefix "$EVAL_PREFIX"
```

The script:
- Lists workflows on the instance whose names contain the eval prefix.
  Deactivates each (via `helpers/deactivate.py` against the workspace's
  YAML if registered, or direct `POST /workflows/{id}/deactivate` if not).
  Then archives via `helpers/archive.py` (or direct
  `POST /workflows/{id}/archive`).
- Lists variables whose names start with the eval prefix. Deletes via
  `helpers/manage_variables.py delete --force`.
- Notes Redis keys: `n8n-lock-evolI-eval-*` and `n8n-ratelimit-evolI-eval-*`
  self-clean via TTL. We do not directly DEL Redis keys — they expire.

After cleanup, take a final snapshot to `$WORKSPACE/.eval/after_cleanup.json`
and confirm the prefix-tagged workflows are gone (or at least archived).

### Step 10 — Persist the result

```bash
mkdir -p "meta-evals/results/${RUN_ID}/${SCENARIO_ID}"
cp -r "$WORKSPACE/.eval/"* "meta-evals/results/${RUN_ID}/${SCENARIO_ID}/"
```

Also save:
- `prompt_sent.txt` — the templated prompt the sub-agent received (so a future
  human can reproduce by hand)
- `transcript.txt` — the sub-agent's full text response
- `before.json`, `after.json`, `after_cleanup.json` — state snapshots
- `grade.json` — the per-criterion + rollup grade

You may delete the `$WORKSPACE/` directory at this point to free disk; the
results dir has everything needed for the report.

## Aggregate report

After all scenarios run, produce the final report:

```bash
python3 meta-evals/runner/report.py aggregate \
  --run-id "$RUN_ID" \
  --results-dir meta-evals/results \
  --scenarios-dir meta-evals/scenarios
```

This writes:
- `meta-evals/results/<RUN_ID>/summary.md` — per-scenario table + aggregates
- `meta-evals/results/<RUN_ID>/replay.md` — how to reproduce this run

## Execution order

Run scenarios in this order to maximize parallelism + minimize state contention:

**Tier 1: Offline (parallelizable)** — 10 scenarios. No n8n contact, fully
isolated. Can spawn all 10 sub-agents simultaneously. Examples:
- bootstrap/init-fresh-project
- authoring/{js,py}-function-via-placeholder
- authoring/static-asset-placeholders
- cloud-functions/{scaffold-fastapi-fn, add-second-fn}
- edge-case/circular-execute-workflow-detected
- prompt-iteration/dspy-optimize-prompt-vs-dataset

**Tier 2: Live-readonly (serialize, but cheap)** — 8 scenarios. Read-only
n8n calls. Run sequentially to keep each sub-agent's view of the instance
consistent. Examples:
- bootstrap/link-credential
- debug/* (4 scenarios)
- resync/* (3 scenarios)
- edge-case/expired-jwt-graceful

**Tier 3: Live-write (strictly serial, with cleanup between)** — 24 scenarios.
Each one creates state on the n8n instance + Redis. Cleanup after every
scenario; do NOT parallelize. Order within tier:
- bootstrap (writes): add-staging-env, manage-variables-crud
- authoring (writes): webhook-codenode-respond, cron-pipeline,
  form-trigger-email, caller-callee-execute-workflow
- resilience (5)
- deploy (5)
- multi-env (3 writes)
- lifecycle (3)
- edge-case (writes): placeholder-sentinel-refused,
  bare-equals-scope-auto-wrapped

Total: 10 (parallel ~5min) + 8 (serial ~10min) + 24 (serial ~50min) = ~65min
wall-clock. Plus aggregate report (~1min).

## Hard-scenario riders

These 3 scenarios need the sub-agent to set up its own prerequisites because
the harness can't pre-inject the right state. The orchestrator passes a
non-empty `{SCENARIO_RIDER}` for each:

| Scenario | Rider |
|---|---|
| `debug/debug-failed-execution-yesterday` | "Yesterday's failed execution doesn't exist yet — set it up first. Create a workflow with a Code node that throws (`throw new Error('eval test')`). Deploy + activate it. Fire the webhook once. Wait 5 seconds for the execution to be recorded as `error`. THEN proceed as if that execution were 'yesterday's failure' and walk through the debug investigation rubric." |
| `prompt-iteration/dspy-optimize-prompt-vs-dataset` | "Set up minimal inputs first: write a 5-example dataset to `n8n-prompts/datasets/sample.jsonl`, a small prompt template to `n8n-prompts/prompts/sample.txt`, and a paired schema. Run `iterate_prompt.py` with `--budget 5` to bound LLM cost. Skip if `OPENROUTER_API_KEY` isn't in the env — emit a `## Self-report` noting the skip and explain you would have run the helper otherwise." |
| `cloud-functions/deploy-cloud-fn-service` | "You don't have Railway CLI auth. Don't attempt `railway up`. Instead, walk through what you'd tell the user step-by-step (login, link, up, capture URL). Identify the exact `cloudFunctionsBaseUrl` placeholder pattern they should add to their env yaml. Document the manual step in your self-report." |

## Anti-gaming check

Once the run completes, grep all transcripts for `meta-evals` references:

```bash
grep -l "meta-evals" "meta-evals/results/${RUN_ID}/"*/transcript.txt
```

Any matches mean a sub-agent snooped the rubric — the prompt template needs
hardening. Document in the run's `summary.md`.

## Failure modes you should NOT do

- Do NOT modify `meta-evals/scenarios/*.md` mid-run. The rubric must be stable
  for the whole run.
- Do NOT modify `helpers/` or `skills/` mid-run. Same reason.
- Do NOT skip cleanup just because a scenario failed — leftover state pollutes
  later scenarios.
- Do NOT commit anything (no `git commit`, no `git push`).
- If a sub-agent times out, mark the scenario `incomplete` in `grade.json`
  with `rollup_score: 0`, run cleanup, continue. Don't retry within a run.
