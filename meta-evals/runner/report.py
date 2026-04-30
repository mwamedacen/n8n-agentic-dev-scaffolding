#!/usr/bin/env python3
"""meta-evals/runner/report.py — aggregate per-scenario grades into final outputs.

Reads `meta-evals/results/<run-id>/<scenario-id>/grade.json` for every
scenario and produces:

  - meta-evals/results/<run-id>/summary.md  (human-readable graded report)
  - meta-evals/results/<run-id>/replay.md   (instructions to reproduce)

Optionally compares against a baseline run if `--baseline <prior-run-id>`
is passed; emits a delta column in the summary table.

Run via:

    python3 meta-evals/runner/report.py aggregate \\
      --run-id 1777999999 \\
      --results-dir meta-evals/results \\
      --scenarios-dir meta-evals/scenarios \\
      [--baseline 1777888888]
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_grade(grade_path: Path) -> dict | None:
    if not grade_path.exists():
        return None
    try:
        return json.loads(grade_path.read_text())
    except Exception:
        return None


def _scenario_metadata(scenarios_dir: Path) -> dict[str, dict]:
    """Return {scenario_id: {category, difficulty, title}} for every scenario file."""
    out: dict[str, dict] = {}
    for md in scenarios_dir.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        fm_match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        if not fm_match:
            continue
        fm = {}
        for line in fm_match.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip()
        sid = fm.get("id")
        if not sid:
            continue
        title_match = re.search(r"^# (.+)$", text, re.MULTILINE)
        out[sid] = {
            "category": fm.get("category", "unknown"),
            "difficulty": fm.get("difficulty", "?"),
            "title": title_match.group(1).strip() if title_match else sid,
        }
    return out


def _short_rationale(grade: dict) -> str:
    """One-sentence summary derived from the grade's tiers."""
    o = grade.get("outcome", {})
    p = grade.get("pitfalls", {})
    n_pass = o.get("n_pass", 0)
    n_resolved = o.get("n_resolved", 0)
    n_total = o.get("n_total", 0)
    n_judge = len(grade.get("needs_orchestrator_judge", []))
    n_pitfalls = len(p.get("hit", []))
    parts = [f"{n_pass}/{n_total} criteria pass"]
    if n_judge:
        parts.append(f"{n_judge} need judge")
    if n_pitfalls:
        parts.append(f"{n_pitfalls} pitfall(s) hit")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------


def build_summary(run_id: str, results_dir: Path, scenarios_dir: Path,
                  baseline_run: str | None) -> str:
    metadata = _scenario_metadata(scenarios_dir)
    grades: dict[str, dict] = {}
    for sid in metadata:
        gpath = results_dir / run_id / sid / "grade.json"
        g = _read_grade(gpath)
        if g is not None:
            grades[sid] = g

    baseline_grades: dict[str, dict] = {}
    if baseline_run:
        for sid in metadata:
            bp = results_dir / baseline_run / sid / "grade.json"
            bg = _read_grade(bp)
            if bg is not None:
                baseline_grades[sid] = bg

    # Aggregate by category
    by_cat: dict[str, list[dict]] = {}
    for sid, g in grades.items():
        cat = metadata[sid]["category"]
        by_cat.setdefault(cat, []).append({"sid": sid, "grade": g})

    lines = []
    lines.append(f"# Eval run `{run_id}` — meta-evals graded report")
    lines.append("")
    lines.append(f"- Date: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Total scenarios graded: **{len(grades)} / {len(metadata)}**")
    if grades:
        avg = sum(g["rollup"]["weighted_score"] for g in grades.values()) / len(grades)
        lines.append(f"- Mean rollup score: **{avg:.3f}**")
        a_count = sum(1 for g in grades.values() if g["rollup"]["letter_grade"] == "A")
        f_count = sum(1 for g in grades.values() if g["rollup"]["letter_grade"] == "F")
        lines.append(f"- Distribution: A×{a_count}, B×{sum(1 for g in grades.values() if g['rollup']['letter_grade']=='B')}, "
                     f"C×{sum(1 for g in grades.values() if g['rollup']['letter_grade']=='C')}, "
                     f"D×{sum(1 for g in grades.values() if g['rollup']['letter_grade']=='D')}, "
                     f"F×{f_count}")
    if baseline_run:
        lines.append(f"- Baseline run for comparison: `{baseline_run}`")
    lines.append("")

    # Per-scenario table
    lines.append("## Per-scenario results")
    lines.append("")
    delta_col = " | Δ" if baseline_run else ""
    lines.append("| ID | Category | Diff | Outcome | Path | Pitfalls | Rollup | Grade | Rationale" + delta_col + " |")
    lines.append("|---|---|---|---|---|---|---|---|---" + ("|---" if baseline_run else "") + "|")
    for cat in sorted(by_cat):
        for entry in sorted(by_cat[cat], key=lambda e: e["sid"]):
            sid = entry["sid"]
            g = entry["grade"]
            meta = metadata[sid]
            row = (
                f"| `{sid}` | {meta['category']} | {meta['difficulty']} "
                f"| {g['outcome']['score']:.2f} | {g['path']['score']:.2f} "
                f"| {g['pitfalls']['score']:.2f} | **{g['rollup']['weighted_score']:.2f}** "
                f"| **{g['rollup']['letter_grade']}** | {_short_rationale(g)}"
            )
            if baseline_run:
                bg = baseline_grades.get(sid)
                if bg:
                    delta = g["rollup"]["weighted_score"] - bg["rollup"]["weighted_score"]
                    arrow = "↑" if delta > 0.01 else ("↓" if delta < -0.01 else "→")
                    row += f" | {arrow} {delta:+.2f}"
                else:
                    row += " | n/a"
            row += " |"
            lines.append(row)
    lines.append("")

    # Aggregate by category
    lines.append("## Aggregate by category")
    lines.append("")
    lines.append("| Category | N | Mean rollup | Pass rate (≥B) |")
    lines.append("|---|---|---|---|")
    for cat in sorted(by_cat):
        rows = by_cat[cat]
        n = len(rows)
        mean = sum(e["grade"]["rollup"]["weighted_score"] for e in rows) / n
        b_or_better = sum(1 for e in rows if e["grade"]["rollup"]["letter_grade"] in ("A", "B")) / n
        lines.append(f"| {cat} | {n} | {mean:.2f} | {b_or_better:.0%} |")
    lines.append("")

    # Top friction observations from sub-agent self-reports
    friction = []
    for sid, g in grades.items():
        sr = g.get("self_report", {})
        unexpected = sr.get("anything_unexpected") if isinstance(sr.get("anything_unexpected"), str) else ""
        if unexpected and unexpected.lower() not in ("none.", "none", "n/a", ""):
            friction.append(f"- **{sid}**: {unexpected.strip().splitlines()[0][:200]}")
    if friction:
        lines.append("## Friction observations (from sub-agents' `anything_unexpected`)")
        lines.append("")
        lines.extend(friction[:10])
        if len(friction) > 10:
            lines.append(f"- … +{len(friction) - 10} more")
        lines.append("")

    # Pitfall hit summary
    all_pitfalls = []
    for sid, g in grades.items():
        for hit in g.get("pitfalls", {}).get("hit", []):
            all_pitfalls.append(f"- **{sid}**: {hit['evidence']} (pitfall: {hit['text'][:100]})")
    if all_pitfalls:
        lines.append("## Pitfalls hit (sub-agents tripped these)")
        lines.append("")
        lines.extend(all_pitfalls)
        lines.append("")

    # Anti-gaming check note
    lines.append("## Anti-gaming check")
    lines.append("")
    lines.append("Run `grep -l 'meta-evals' " + str(results_dir / run_id) +
                 "/*/transcript.txt` after the run; any matches mean a sub-agent "
                 "snooped the rubric and the prompt template needs hardening.")
    lines.append("")

    # Self-preference disclosure
    lines.append("## Bias disclosure")
    lines.append("")
    lines.append(
        "This eval grades Claude Code's behavior using Claude Code as the orchestrator-judge "
        "for behavioral criteria. Self-preference bias is a known confound. "
        "Mitigation: the outcome tier is fully rule-based; orchestrator-judge applies only "
        "to the smaller path-discipline + behavioral tiers (≤30% of the rollup weight)."
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Replay instructions
# ---------------------------------------------------------------------------


def build_replay(run_id: str, scenarios_dir: Path) -> str:
    metadata = _scenario_metadata(scenarios_dir)
    n = len(metadata)
    lines = [
        f"# Replay instructions for run `{run_id}`",
        "",
        f"This run executed **{n} scenarios** under `meta-evals/scenarios/`. ",
        "To reproduce, you need:",
        "",
        "- This harness checked out at the same git SHA used for the original run.",
        "- A working `.env` file with `N8N_API_KEY` and `N8N_INSTANCE_NAME`.",
        "  (For the original audit, that was `.env.bak.dod` at the repo root.)",
        "- Disk for `/tmp/eval-<run-id>/` workspaces (~50MB per scenario).",
        "- Wall-clock ~75 minutes for all 42 scenarios serialized.",
        "",
        "## Section 1 — Replay with Claude Code (default)",
        "",
        "```bash",
        "cd /path/to/n8n-evol-I",
        "claude   # opens an interactive session in the repo",
        "```",
        "",
        "Then paste this user message:",
        "",
        "> Read meta-evals/runner/orchestrate.md and execute it. ",
        "> Use .env.bak.dod as the credential source. ",
        "> RUN_ID = <fresh-timestamp>.",
        "",
        "The orchestrator (Claude Code itself) will spawn one sub-agent per scenario via its `Agent` tool, "
        "capture each one's transcript, grade via `grade.py`, clean up via `cleanup.py`, and aggregate via `report.py`.",
        "",
        "## Section 2 — Replay one scenario manually",
        "",
        "```bash",
        "SCENARIO_ID=init-fresh-project   # or any other id",
        "PROMPT=$(awk '/^## Prompt/,/^## /' meta-evals/scenarios/*/${SCENARIO_ID}.md | sed '1d;$d')",
        "echo \"$PROMPT\" | claude -p \"$(cat -)\"",
        "```",
        "",
        "(then grade by hand against the scenario's `## Success criteria` section)",
        "",
        "## Section 3 — Replay with a different agent product",
        "",
        "The eval is agent-agnostic at the *grading* layer. To swap out the inner agent:",
        "",
        "1. Replace the `Agent(...)` call in `orchestrate.md` step 5 with your tool's invocation. ",
        "   The orchestrator only needs the sub-agent's stdout text — no other I/O.",
        "2. Keep the sub-agent prompt template (`sub_agent_prompt.md`) unchanged.",
        "3. Keep `grade.py`, `cleanup.py`, `state.py`, `report.py` unchanged — they don't care which agent ran.",
        "",
        "### Example invocation patterns (verify with each tool's current docs)",
        "",
        "**Aider** — `echo \"$PROMPT\" | aider --message - --no-auto-commits`",
        "",
        "**Continue CLI** — `cn -p \"$PROMPT\" --output-format json`",
        "",
        "**Anthropic Agent SDK (Python)** — programmatic via `client.beta.agents.create()` + ",
        "`sessions.events.send()`. See https://docs.claude.com/en/docs/agents/agent-sdk.",
        "",
        "**Hermes / Antigravity / OpenAI Codex CLI** — at the time of this run, these were not ",
        "confirmed to exist as standalone, non-interactive CLI products. If your tool offers a ",
        "non-interactive `--prompt`-style flag, use the **generic CLI template**:",
        "",
        "```bash",
        "<your-tool> --prompt-file - --workdir \"$WORKSPACE\" < <(echo \"$PROMPT\") > transcript.txt",
        "```",
        "",
        "Then point `orchestrate.md` step 5 at this command instead of the `Agent` tool.",
        "",
        "## Section 4 — Replay manually (no automation)",
        "",
        "If you have no programmable agent, walk the suite by hand:",
        "",
        "```bash",
        "python3 meta-evals/runner.py   # the existing checklist scaffolder",
        "```",
        "",
        "Per scenario: open a fresh agent session, paste the `## Prompt` body, observe behavior, ",
        "grade against `## Success criteria` + `## Pitfalls`, mark in the checklist.",
        "",
        "## Anti-gaming reminder",
        "",
        "**Never expose any of these to the agent under test:**",
        "",
        "- The scenario's `## Success criteria` section",
        "- The scenario's `## Pitfalls` section",
        "- The scenario's `## Expected helpers invoked` section",
        "- This `replay.md` file",
        "- The `meta-evals/runner/grade.py` source",
        "",
        "Only `## Prompt` is safe to pass to the agent. The rubric stays with the orchestrator.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("aggregate", help="Build summary.md and replay.md for a run.")
    p.add_argument("--run-id", required=True)
    p.add_argument("--results-dir", required=True, type=Path)
    p.add_argument("--scenarios-dir", required=True, type=Path)
    p.add_argument("--baseline", default=None,
                   help="Optional prior run-id to compute deltas against.")

    args = parser.parse_args()
    if args.cmd != "aggregate":
        parser.error(f"unknown subcommand {args.cmd}")

    out_dir = args.results_dir / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = build_summary(args.run_id, args.results_dir, args.scenarios_dir, args.baseline)
    (out_dir / "summary.md").write_text(summary)
    print(f"Wrote {out_dir / 'summary.md'}")

    replay = build_replay(args.run_id, args.scenarios_dir)
    (out_dir / "replay.md").write_text(replay)
    print(f"Wrote {out_dir / 'replay.md'}")


if __name__ == "__main__":
    main()
