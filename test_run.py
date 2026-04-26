"""run.py CLI tests: -c shape, --env, illegal flag combinations."""
import os
import subprocess
import sys
import pytest

REPO = os.path.dirname(os.path.abspath(__file__))


def _run(*args, env_extra=None):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["n8n-harness", *args],
        capture_output=True, text=True, env=env, cwd=REPO,
    )


def test_help_exits_zero():
    r = _run("--help")
    assert r.returncode == 0
    assert "n8n-harness" in r.stdout


def test_version():
    r = _run("--version")
    assert r.returncode == 0
    assert r.stdout.strip() == "0.1.0"


def test_c_executes_snippet():
    r = _run("-c", "print('hello-from-c')")
    assert r.returncode == 0, r.stderr
    assert "hello-from-c" in r.stdout


def test_c_does_not_read_stdin():
    """Pass stdin content; -c should not block waiting for it."""
    r = subprocess.run(
        ["n8n-harness", "-c", "print('ok')"],
        input="this should not be read",
        capture_output=True, text=True, cwd=REPO, timeout=10,
    )
    assert r.returncode == 0
    assert r.stdout.strip() == "ok"


def test_env_flag_picks_environment():
    """--env <name> sets N8H_ENV in the snippet's runtime."""
    r = _run("--env", "prod", "-c", "print(os.environ['N8H_ENV'])")
    assert r.returncode == 0
    assert r.stdout.strip() == "prod"


def test_env_unknown_exits_2():
    r = _run("--env", "doesnotexist", "-c", "print('x')")
    assert r.returncode == 2
    assert "unknown env" in (r.stderr + r.stdout)


def test_unknown_flag_exits_2():
    r = _run("--no-such-flag")
    assert r.returncode == 2


def test_illegal_combo_c_with_doctor_exits_2():
    """-c is incompatible with --doctor / --setup / --update / --reload / --version / --help.

    Pre-scan in run.py rejects illegal combos symmetrically (regardless of arg order).
    """
    # Both orders should reject:
    for args in (("-c", "print('x')", "--doctor"), ("--doctor", "-c", "print('x')")):
        r = _run(*args)
        assert r.returncode == 2, f"expected 2, got {r.returncode} for args={args}\nstderr:\n{r.stderr}"


def test_list_envs():
    r = _run("--list-envs")
    assert r.returncode == 0
    assert "dev" in r.stdout.splitlines()
