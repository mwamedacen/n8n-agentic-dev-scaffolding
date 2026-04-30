#!/usr/bin/env python3
"""meta-evals/runner.py — scenario-iteration scaffolder.

NOT an execution engine. Reads every scenario file under scenarios/<category>/
and prints a checklist scaffold for human / agent operators iterating through
the suite. Pipe to a file, fill in pass/fail per scenario, commit the result
to your eval-tracking system.

Usage:
    python3 meta-evals/runner.py [--category <name>] [--difficulty <level>]
"""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCENARIOS_DIR = ROOT / "scenarios"


def _parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def _extract_first_heading(text: str) -> str:
    m = re.search(r"^# (.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else "(no title)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", default=None, help="Filter by category")
    parser.add_argument("--difficulty", default=None, help="Filter by difficulty")
    args = parser.parse_args()

    scenarios = sorted(SCENARIOS_DIR.rglob("*.md"))
    by_category: dict[str, list[tuple[str, str, str]]] = {}
    for path in scenarios:
        text = path.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        if args.category and fm.get("category") != args.category:
            continue
        if args.difficulty and fm.get("difficulty") != args.difficulty:
            continue
        category = fm.get("category", "unknown")
        title = _extract_first_heading(text)
        scenario_id = fm.get("id", path.stem)
        difficulty = fm.get("difficulty", "?")
        by_category.setdefault(category, []).append((scenario_id, title, difficulty))

    total = sum(len(v) for v in by_category.values())
    print(f"# meta-evals checklist — {total} scenarios\n")
    if not by_category:
        print("(no scenarios match the given filters)")
        return
    for category in sorted(by_category):
        print(f"## {category} ({len(by_category[category])})\n")
        for sid, title, diff in by_category[category]:
            print(f"- [ ] **{sid}** ({diff}) — {title}")
        print()
    print("---\n")
    print("Run order: trivial → easy → medium → hard → expert. Per-scenario,")
    print("paste its `Prompt` section into a fresh agent session, observe behavior,")
    print("grade against `Success criteria`, mark above. Don't autograde — the")
    print("eval is about the agent's path, not just the output.")


if __name__ == "__main__":
    main()
