#!/usr/bin/env python3
"""meta-evals/runner/grade.py — per-scenario grader.

Reads a scenario MD's hidden rubric (Success criteria, Pitfalls, Expected
helpers invoked, Expected skills consulted) and produces a structured
grade.json by walking each rubric bullet against:

  - the sub-agent's transcript
  - the sub-agent's workspace (filesystem)
  - the n8n state diff (before vs after)

Output structure:

    {
      "scenario_id": "...",
      "outcome": {
        "criteria": [
          {"text": "...", "kind": "fs|regex|state|behavioral",
           "pass": true|false|null,
           "requires_judge": false,
           "evidence": "..."},
          ...
        ],
        "score": 0.0..1.0,                    # mean of resolved criteria
        "n_total": int,
        "n_resolved": int,                     # excludes requires_judge==null
        "n_pass": int,
      },
      "path": {
        "expected_helpers": [...],
        "matched_helpers": [...],
        "extras": [...],                       # commands run that weren't expected
        "score": 0.0..1.0,
      },
      "pitfalls": {
        "documented": [...],
        "hit": [{"text": "...", "evidence": "..."}, ...],
        "score": 0.0..1.0,                     # 1 - (n_hit / n_documented)
      },
      "self_report": {
        "skills_consulted": [...],
        "helpers_invoked": [...],
        "artifacts": [...],
        "n8n_state_changes": [...],
        "self_assessment": "...",
        "anything_unexpected": "...",
      },
      "rollup": {
        "weighted_score": 0.0..1.0,            # 0.7*outcome + 0.2*path + 0.1*pitfalls
        "letter_grade": "A|B|C|D|F",
      },
      "needs_orchestrator_judge": [criterion_index, ...]  # which to fill in via prompt-reasoning
    }

The orchestrator post-processes this file: for each criterion in
`needs_orchestrator_judge`, it reads the transcript and applies its own
judgment, then updates the criterion in place and re-runs the rollup.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Make sibling modules importable (state.py).
sys.path.insert(0, str(Path(__file__).resolve().parent))


# ---------------------------------------------------------------------------
# Scenario file parsing
# ---------------------------------------------------------------------------


def _read_scenario(scenarios_dir: Path, scenario_id: str) -> tuple[Path, str]:
    """Locate the scenario file by id (recursive search). Return (path, body)."""
    for md in scenarios_dir.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        if not m:
            continue
        fm_block = m.group(1)
        if re.search(rf"^\s*id\s*:\s*{re.escape(scenario_id)}\s*$", fm_block, re.MULTILINE):
            return md, text
    raise FileNotFoundError(f"No scenario with id '{scenario_id}' under {scenarios_dir}")


def _extract_section(text: str, heading: str) -> str:
    """Extract the body of a `## <heading>` section. Empty string if missing."""
    pattern = rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s+|\Z)"
    m = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _parse_bullets(section_text: str) -> list[str]:
    """Pull markdown bullet items (`- ...` or `- [ ] ...`) from a section."""
    out: list[str] = []
    for line in section_text.splitlines():
        line = line.rstrip()
        m = re.match(r"^\s*-\s+(?:\[[ xX]?\]\s+)?(.+)$", line)
        if m:
            out.append(m.group(1).strip())
    return out


# ---------------------------------------------------------------------------
# Self-report parsing (sub-agent's own structured output)
# ---------------------------------------------------------------------------


def _parse_self_report(transcript: str) -> dict:
    """Pull the Self-report section from the sub-agent's transcript."""
    m = re.search(r"##\s+Self-report\b(.*)$", transcript, re.DOTALL | re.IGNORECASE)
    if not m:
        return {
            "skills_consulted": [],
            "helpers_invoked": [],
            "artifacts": [],
            "n8n_state_changes": [],
            "self_assessment": "",
            "anything_unexpected": "",
            "_present": False,
        }
    body = m.group(1)
    fields = ("skills_consulted", "helpers_invoked", "artifacts_created_or_modified",
              "n8n_state_changes", "self_assessment", "anything_unexpected")
    out: dict[str, Any] = {"_present": True}
    for fname in fields:
        sub = re.search(rf"###\s+{re.escape(fname)}\s*\n(.*?)(?=\n###\s+|\Z)",
                        body, re.DOTALL | re.IGNORECASE)
        section = sub.group(1).strip() if sub else ""
        # Treat as bullet-list if it contains "- " bullets, otherwise free text.
        if re.search(r"^\s*-\s+", section, re.MULTILINE):
            out[fname] = _parse_bullets(section)
        else:
            out[fname] = section
    # Normalize key name
    out["artifacts"] = out.pop("artifacts_created_or_modified", [])
    return out


# ---------------------------------------------------------------------------
# Outcome tier — classify and evaluate each Success-criteria bullet
# ---------------------------------------------------------------------------


_FS_RE = re.compile(r"`?([^\s`]+/[^\s`]*?)`?\s+exists?", re.IGNORECASE)
_HELPER_RE = re.compile(r"`?(python3\s+\S+helpers/\S+\.py[^`]*?)`?\s+(?:exits?\s+0|succeeds)",
                        re.IGNORECASE)
_STATE_PHRASES = (
    "deployed and activated", "workflow deployed", "execution recorded",
    "workflow exists with", "no new executions", "execution status",
    "workflow archived", "workflow unarchived", "variable created",
    "variable deleted", "executions visible", "shows it's reachable",
    "execution recorded", "execution from yesterday",
)
_BEHAVIORAL_PHRASES = (
    "agent points", "agent identifies", "agent does not", "agent does NOT",
    "agent surfaces", "agent recognizes", "agent refuses", "agent reads",
    "agent walks", "tells the user", "agent should",
)


def _classify_criterion(text: str) -> str:
    """Return one of: 'fs', 'regex', 'state', 'helper', 'behavioral', 'unknown'."""
    low = text.lower()
    if _HELPER_RE.search(text):
        return "helper"
    if _FS_RE.search(text):
        return "fs"
    if any(p.lower() in low for p in _STATE_PHRASES):
        return "state"
    if any(p in text for p in _BEHAVIORAL_PHRASES):
        return "behavioral"
    if "regex" in low or "matches" in low or "contains" in low:
        return "regex"
    return "unknown"


def _eval_fs_criterion(text: str, workspace: Path) -> tuple[bool | None, str]:
    """Resolve `<workspace>/<path> exists`. Returns (pass, evidence)."""
    m = _FS_RE.search(text)
    if not m:
        return None, "could not parse path"
    rel = m.group(1).strip()
    # Strip placeholder prefixes used in scenario writing — do this BEFORE
    # rstripping the trailing slash, otherwise the prefix `foo/` won't match.
    for prefix in ("<workspace>/", "n8n-evol-I-workspace/"):
        if rel.startswith(prefix):
            rel = rel[len(prefix):]
    rel = rel.rstrip("/").lstrip("/")
    if rel in ("", "."):
        # The criterion meant "the workspace exists" (root). True by definition
        # if we got this far — workspace was provisioned by the orchestrator.
        return workspace.exists(), f"workspace_root={workspace} exists={workspace.exists()}"
    target = workspace / rel
    return target.exists(), f"path={target} exists={target.exists()}"


def _eval_state_criterion(text: str, diff: dict) -> tuple[bool | None, str]:
    """Best-effort heuristic for state-shaped criteria using the snapshot diff.

    We don't try to be exhaustive — if the criterion mentions 'deployed and
    activated' and the diff shows ≥1 added or state-changed workflow, mark
    pass. If it mentions 'execution recorded' and ≥1 new_execution, pass. The
    grader's rule-based pass is signal; the orchestrator can override via
    judge if the heuristic is wrong.
    """
    low = text.lower()
    s = diff.get("summary", {}) if diff else {}
    if "deployed" in low or "activated" in low or "deploy" in low:
        ok = (s.get("n_added_workflows", 0) + s.get("n_state_changed_workflows", 0)) > 0
        return ok, f"added_or_state_changed_workflows={s.get('n_added_workflows', 0)}+{s.get('n_state_changed_workflows', 0)}"
    if "execution recorded" in low or "executions visible" in low or "successful execution" in low:
        ok = s.get("n_new_executions", 0) > 0
        return ok, f"new_executions={s.get('n_new_executions', 0)}"
    if "archived" in low and "unarchived" not in low:
        ok = s.get("n_state_changed_workflows", 0) > 0
        return ok, f"state_changed_workflows={s.get('n_state_changed_workflows', 0)}"
    if "variable created" in low:
        ok = s.get("n_added_variables", 0) > 0
        return ok, f"added_variables={s.get('n_added_variables', 0)}"
    if "variable deleted" in low or "variable absent" in low:
        ok = s.get("n_removed_variables", 0) > 0
        return ok, f"removed_variables={s.get('n_removed_variables', 0)}"
    return None, "no state heuristic matched"


def _eval_helper_criterion(text: str, transcript: str) -> tuple[bool | None, str]:
    """Resolve 'python3 <harness>/helpers/X.py ... exits 0' — confirmed if the
    transcript shows the command ran without an exception traceback nearby."""
    m = _HELPER_RE.search(text)
    if not m:
        return None, "could not parse helper command"
    cmd = m.group(1)
    # Look for the script name in the transcript; weak signal but useful.
    script = re.search(r"helpers/(\w+)\.py", cmd)
    if script and script.group(1) in transcript:
        # Heuristic: if Traceback appears within 200 chars after the command,
        # call it a fail.
        idx = transcript.find(script.group(1))
        window = transcript[idx:idx + 500]
        if "Traceback" in window:
            return False, f"helper {script.group(1)} ran but traceback nearby"
        return True, f"helper {script.group(1)} executed without nearby traceback"
    return False, "helper command not found in transcript"


def _eval_outcome(scenario_text: str, workspace: Path, transcript: str,
                  diff: dict) -> dict:
    """Walk Success criteria bullets; return outcome tier."""
    section = _extract_section(scenario_text, "Success criteria")
    bullets = _parse_bullets(section)
    criteria_out = []
    n_pass = 0
    n_resolved = 0
    needs_judge: list[int] = []
    for idx, bullet in enumerate(bullets):
        kind = _classify_criterion(bullet)
        passed: bool | None = None
        evidence = ""
        if kind == "fs":
            passed, evidence = _eval_fs_criterion(bullet, workspace)
        elif kind == "helper":
            passed, evidence = _eval_helper_criterion(bullet, transcript)
        elif kind == "state":
            passed, evidence = _eval_state_criterion(bullet, diff)
        elif kind == "regex":
            # Lookup the literal text in the transcript as a weak heuristic.
            passed = bullet.lower() in transcript.lower()
            evidence = "literal-text scan of transcript"
        elif kind == "behavioral":
            passed = None  # defer to orchestrator
            evidence = "behavioral — orchestrator-as-judge required"
        else:
            passed = None
            evidence = "unknown criterion shape — orchestrator-as-judge required"

        requires_judge = passed is None
        if requires_judge:
            needs_judge.append(idx)
        else:
            n_resolved += 1
            if passed:
                n_pass += 1

        criteria_out.append({
            "index": idx,
            "text": bullet,
            "kind": kind,
            "pass": passed,
            "requires_judge": requires_judge,
            "evidence": evidence,
            "notes": "",
        })

    score = (n_pass / n_resolved) if n_resolved > 0 else 0.0
    return {
        "criteria": criteria_out,
        "score": score,
        "n_total": len(bullets),
        "n_resolved": n_resolved,
        "n_pass": n_pass,
        "needs_judge_indices": needs_judge,
    }


# ---------------------------------------------------------------------------
# Path tier — overlap between expected helpers and what was actually run
# ---------------------------------------------------------------------------


# Match a helper reference with or without the `python3 <path>` prefix.
# Both `python3 .../helpers/foo.py` and a bare ``helpers/foo.py`` in a bullet
# count. The grader uses the helper's basename (sans .py) for set-overlap
# comparison.
_HELPER_REF_RE = re.compile(r"helpers/(\w+)\.py", re.IGNORECASE)
# In a transcript we additionally want the command to look like an actual
# invocation, not e.g. a doc reference. Either `python3 ... helpers/foo.py`
# or a fenced-bash code block containing the helper name suffices.
_HELPER_INVOKE_RE = re.compile(r"python3\s+\S*helpers/(\w+)\.py", re.IGNORECASE)


def _eval_path(scenario_text: str, transcript: str, self_report: dict) -> dict:
    section = _extract_section(scenario_text, "Expected helpers invoked")
    expected_bullets = _parse_bullets(section)
    expected_helpers: list[str] = []
    for b in expected_bullets:
        for m in _HELPER_REF_RE.finditer(b):
            name = m.group(1)
            if name not in expected_helpers:
                expected_helpers.append(name)

    # Actual: prefer real invocation pattern; fall back to plain helper-ref
    # mentions for transcripts that show the command without `python3`.
    actual_set = set(_HELPER_INVOKE_RE.findall(transcript))
    if not actual_set:
        actual_set = set(_HELPER_REF_RE.findall(transcript))
    actual_helpers = sorted(actual_set)
    # Also extract from the self-report "helpers_invoked" field if structured.
    sr_helpers = self_report.get("helpers_invoked", [])
    if isinstance(sr_helpers, list):
        for line in sr_helpers:
            for m in _HELPER_REF_RE.finditer(line):
                name = m.group(1)
                if name not in actual_helpers:
                    actual_helpers.append(name)

    matched = [h for h in expected_helpers if h in actual_helpers]
    extras = [h for h in actual_helpers if h not in expected_helpers]
    score = (len(matched) / len(expected_helpers)) if expected_helpers else 1.0
    return {
        "expected_helpers": expected_helpers,
        "actual_helpers": actual_helpers,
        "matched_helpers": matched,
        "extras": extras,
        "score": score,
    }


# ---------------------------------------------------------------------------
# Pitfall tier — grep transcript for documented failure modes
# ---------------------------------------------------------------------------


# Common pitfall signatures. Maps a substring/regex in a pitfall bullet to a
# detector that scans the transcript for evidence the agent tripped it.
_PITFALL_DETECTORS: list[tuple[re.Pattern, re.Pattern, str]] = [
    # (pitfall-text-regex, transcript-evidence-regex, evidence-message)
    (re.compile(r"--force", re.IGNORECASE),
     re.compile(r"--force\b"),
     "agent passed --force"),
    (re.compile(r"\bcommit\b", re.IGNORECASE),
     re.compile(r"\bgit\s+commit\b"),
     "agent ran git commit"),
    (re.compile(r"\bpush\b", re.IGNORECASE),
     re.compile(r"\bgit\s+push\b"),
     "agent ran git push"),
    (re.compile(r"bare-?=", re.IGNORECASE),
     re.compile(r'--scope-expression\s+"=\w'),  # scope starts with =word, not ={{
     "agent used bare-= scope (auto-wrapped, but warns)"),
    (re.compile(r"sentinel|placeholder", re.IGNORECASE),
     re.compile(r'workflows\.\w+\.id.*placeholder', re.IGNORECASE),
     "sentinel id leaked into substitution"),
]


def _eval_pitfalls(scenario_text: str, transcript: str) -> dict:
    section = _extract_section(scenario_text, "Pitfalls")
    bullets = _parse_bullets(section)
    hits = []
    for bullet in bullets:
        for pf_re, ev_re, ev_msg in _PITFALL_DETECTORS:
            if pf_re.search(bullet) and ev_re.search(transcript):
                hits.append({
                    "text": bullet,
                    "evidence": ev_msg,
                })
                break
    score = 1.0 - (len(hits) / max(1, len(bullets)))
    return {
        "documented": bullets,
        "hit": hits,
        "score": score,
    }


# ---------------------------------------------------------------------------
# Rollup
# ---------------------------------------------------------------------------


def _letter_grade(weighted: float) -> str:
    pct = weighted * 100
    if pct >= 85:
        return "A"
    if pct >= 70:
        return "B"
    if pct >= 55:
        return "C"
    if pct >= 40:
        return "D"
    return "F"


def _rollup(outcome: dict, path: dict, pitfalls: dict) -> dict:
    weighted = 0.7 * outcome["score"] + 0.2 * path["score"] + 0.1 * pitfalls["score"]
    return {
        "weighted_score": round(weighted, 4),
        "letter_grade": _letter_grade(weighted),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("grade", help="Grade one scenario.")
    p.add_argument("--scenario-id", required=True)
    p.add_argument("--scenarios-dir", required=True, type=Path,
                   help="Path to meta-evals/scenarios.")
    p.add_argument("--workspace", required=True, type=Path,
                   help="Sub-agent's workspace.")
    p.add_argument("--transcript", required=True, type=Path,
                   help="Sub-agent's transcript text file.")
    p.add_argument("--before", type=Path, default=None,
                   help="Pre-scenario state snapshot (for live scenarios).")
    p.add_argument("--after", type=Path, default=None,
                   help="Post-scenario state snapshot (for live scenarios).")
    p.add_argument("--eval-prefix", default="evolI-eval",
                   help="Prefix used by the sub-agent for created artifacts.")
    p.add_argument("--output", required=True, type=Path,
                   help="Where to write grade.json.")

    args = parser.parse_args()

    if args.cmd != "grade":
        parser.error(f"unknown subcommand {args.cmd}")

    scenario_path, scenario_text = _read_scenario(args.scenarios_dir, args.scenario_id)
    transcript = args.transcript.read_text(encoding="utf-8")

    diff: dict = {}
    if args.before and args.after and args.before.exists() and args.after.exists():
        # Load + compute the diff inline (avoid shelling out to state.py).
        from state import diff as state_diff  # type: ignore
        before = json.loads(args.before.read_text())
        after = json.loads(args.after.read_text())
        diff = state_diff(before, after)

    self_report = _parse_self_report(transcript)
    outcome = _eval_outcome(scenario_text, args.workspace, transcript, diff)
    path = _eval_path(scenario_text, transcript, self_report)
    pitfalls = _eval_pitfalls(scenario_text, transcript)
    rollup = _rollup(outcome, path, pitfalls)

    grade = {
        "scenario_id": args.scenario_id,
        "scenario_path": str(scenario_path),
        "outcome": outcome,
        "path": path,
        "pitfalls": pitfalls,
        "self_report": self_report,
        "rollup": rollup,
        "needs_orchestrator_judge": outcome["needs_judge_indices"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(grade, indent=2))
    s = grade["rollup"]
    print(f"Graded {args.scenario_id}: rollup={s['weighted_score']} "
          f"grade={s['letter_grade']} "
          f"(outcome={outcome['score']:.2f} path={path['score']:.2f} "
          f"pitfalls={pitfalls['score']:.2f}; "
          f"{len(grade['needs_orchestrator_judge'])} criteria need judge)")


if __name__ == "__main__":
    main()
