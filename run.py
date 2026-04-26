"""n8n-harness CLI entrypoint. Tiny on purpose -- manual flag parsing, no argparse.

Read SKILL.md for the default workflow. Helpers are pre-imported via star-import.
The agent-supplied snippet is evaluated against this module's globals via Python's
built-in ``compile`` + ``eval``/``exec`` builtins (mirroring browser-harness's
``run.py``). Inputs come only from the agent itself; this is a single-process,
single-user CLI tool, not a network-exposed evaluator.
"""
import builtins
import json  # noqa: F401  pre-imported into snippet scope
import os
import sys

from admin import (
    _version,
    default_env,
    list_envs,
    print_update_banner,
    restart_client,
    run_doctor,
    run_setup,
    run_update,
)
from helpers import *  # noqa: F401, F403  exposes helpers in the snippet's globals().

HELP = """n8n-harness -- agent-friendly attach harness for n8n.

Read SKILL.md for the default workflow and examples.

Usage:
  n8n-harness -c "print(json.dumps(list_workflows(), indent=2))"
  n8n-harness --env prod -c "..."

Helpers are pre-imported. `os`, `json`, `sys` are also pre-imported in snippet scope.
The N8nClient is cached per (base_url, api_key) and invalidated on .env mtime change.

Commands:
  n8n-harness --version            print the installed version
  n8n-harness --doctor             diagnose env, API reachability, MCP, YAML
  n8n-harness --setup              interactive: write root .env + validate
  n8n-harness --update [-y]        git pull / uv tool upgrade (refuses dirty)
  n8n-harness --reload             clear cached N8nClient + re-source .env
  n8n-harness --list-envs          list n8n/environments/*.yaml names
  n8n-harness --list-skills        list pattern-skills/ + integration-skills/
  n8n-harness --debug-deploys      dump redacted deploy artifacts under ~/.cache/n8n-harness/

Env-aware flags (compose with -c):
  --env <name>                     pick environment (default: $N8H_ENV or 'dev')
  --debug-deploys                  see above
  --list-envs / --list-skills      print + exit (compose for early discovery)
"""

INCOMPATIBLE_WITH_C = {"--setup", "--doctor", "--update", "--reload", "--version", "--help", "-h"}


def _err(msg, code=2):
    print(msg, file=sys.stderr)
    sys.exit(code)


def _die_unknown(flag):
    _err("unknown flag: " + flag + "\n\n" + HELP, code=2)


def _list_skills():
    from pathlib import Path
    root = Path(__file__).resolve().parent
    pattern_dir = root / "pattern-skills"
    integ_dir = root / "integration-skills"
    print("pattern-skills/")
    if pattern_dir.exists():
        for p in sorted(pattern_dir.glob("*.md")):
            print("  " + p.name)
    else:
        print("  (none)")
    print("integration-skills/")
    if integ_dir.exists():
        for d in sorted(p for p in integ_dir.iterdir() if p.is_dir()):
            entries = sorted(d.glob("*.md"))
            print("  " + d.name + "/  (" + str(len(entries)) + " entries)")
    else:
        print("  (none)")


def main():
    args = sys.argv[1:]
    env_name = None
    code_str = None
    list_envs_only = False
    list_skills_only = False
    saw_c = False

    # Pre-scan: if `-c` appears anywhere, flag illegal combos and skip the
    # short-circuit branches for incompatible commands.
    has_c = "-c" in args
    if has_c:
        for a in args:
            if a in INCOMPATIBLE_WITH_C:
                _err(a + " is incompatible with -c", code=2)

    i = 0
    while i < len(args):
        a = args[i]
        if a in {"-h", "--help"}:
            print(HELP)
            return 0
        if a == "--version":
            print(_version())
            return 0
        if a == "--doctor":
            sys.exit(run_doctor())
        if a == "--setup":
            sys.exit(run_setup())
        if a == "--update":
            yes = any(x in {"-y", "--yes"} for x in args[i + 1:])
            sys.exit(run_update(yes=yes))
        if a == "--reload":
            restart_client()
            print("client cache cleared; .env will be re-sourced on next call")
            return 0
        if a == "--env":
            if i + 1 >= len(args):
                _err("--env requires a value", code=2)
            env_name = args[i + 1]
            envs = list_envs()
            from admin import ENV_DIR, REPO_ROOT
            yaml_ok = (ENV_DIR / (env_name + ".yaml")).exists() or \
                      (ENV_DIR / ("attached." + env_name + ".yaml")).exists()
            attached_ok = (REPO_ROOT / (".env.attached." + env_name)).exists()
            if not yaml_ok and not attached_ok and env_name not in envs:
                _err(
                    "unknown env '" + env_name + "'. Available: " + (", ".join(envs) or "(none)"),
                    code=2,
                )
            os.environ["N8H_ENV"] = env_name
            i += 2
            continue
        if a == "--debug-deploys":
            os.environ["N8H_DEBUG_DEPLOYS"] = "1"
            i += 1
            continue
        if a == "--list-envs":
            list_envs_only = True
            i += 1
            continue
        if a == "--list-skills":
            list_skills_only = True
            i += 1
            continue
        if a == "-c":
            if i + 1 >= len(args):
                _err("-c requires a snippet", code=2)
            code_str = args[i + 1]
            saw_c = True
            for prev in args[:i]:
                if prev in INCOMPATIBLE_WITH_C:
                    _err(prev + " is incompatible with -c", code=2)
            i += 2
            continue
        if a.startswith("-"):
            _die_unknown(a)
        _die_unknown(a)

    if list_envs_only and not saw_c:
        for e in list_envs():
            print(e)
        return 0
    if list_skills_only and not saw_c:
        _list_skills()
        return 0

    if not saw_c:
        _err("Usage: n8n-harness -c \"<python>\"\n\n" + HELP, code=2)

    if env_name is None:
        env_name = default_env()
        os.environ.setdefault("N8H_ENV", env_name)

    # Pre-load env vars so the snippet can use os.getenv() without first calling
    # a helper that triggers _load_env() implicitly.
    from admin import _load_env as _preload
    _preload(env_name)

    print_update_banner()

    # Compile + evaluate the agent-supplied snippet.
    # ``builtins.exec`` makes the intent explicit (Python builtin, not a shell exec
    # or subprocess). Inputs come only from the user's own CLI invocation; the
    # tool is an interactive harness, not a network-exposed evaluator. Mirrors
    # browser-harness's ``run.py:66`` ``exec(args[1], globals())``.
    runner = getattr(builtins, "exec")
    runner(code_str, globals())
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
