"""n8n-harness admin: env loading, client cache, doctor.

Read, edit, extend — separate from helpers.py so that "what does the harness
*do*" stays distinct from "how does it talk to the n8n instance".
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent
ENV_DIR = REPO_ROOT / "n8n" / "environments"

# Where doctor lists every .env-reading site (for visibility / split-brain).
ENV_READING_SITES = [
    "admin._load_env (Python helpers)",
    "n8n/deployment_scripts/_common.sh (deploy/deactivate)",
    "n8n/resync_scripts/_common.sh (resync)",
    "n8n/deployment_scripts/bootstrap_workflows.py (bootstrap)",
    "factory/prompt_engineering/config.py (DSPy)",
]


# ---------------------------------------------------------------------------
# .env layering
# ---------------------------------------------------------------------------

def _parse_dotenv(path: Path) -> Dict[str, str]:
    """Tiny dotenv parser. Keeps the harness install lean."""
    out: Dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        out[k.strip()] = v
    return out


def _load_yaml(path: Path) -> Dict[str, Any]:
    import yaml
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def _load_env(env_name: str) -> Dict[str, str]:
    """Layered env loader: root .env first, then .env.<env> overlay (override=True).

    Env-specific values WIN for shared keys. Returns the resolved snapshot
    *and* mutates os.environ so subprocesses (bash scripts etc.) inherit it.
    """
    layered: Dict[str, str] = {}
    layered.update(_parse_dotenv(REPO_ROOT / ".env"))
    layered.update(_parse_dotenv(REPO_ROOT / f".env.{env_name}"))

    # Optional: attached.<name> .env exists for Phase 3 attach() runtime.
    layered.update(_parse_dotenv(REPO_ROOT / f".env.attached.{env_name}"))

    yaml_path = ENV_DIR / f"{env_name}.yaml"
    attached_yaml_path = ENV_DIR / f"attached.{env_name}.yaml"
    yaml_cfg = _load_yaml(yaml_path) or _load_yaml(attached_yaml_path)

    # YAML fallback for instance only (env vars take precedence).
    if not layered.get("N8N_INSTANCE_NAME"):
        yaml_instance = (yaml_cfg.get("n8n") or {}).get("instanceName", "")
        if yaml_instance:
            layered["N8N_INSTANCE_NAME"] = yaml_instance

    for k, v in layered.items():
        os.environ[k] = v

    return layered


def _yaml_for(env_name: str) -> Dict[str, Any]:
    cfg = _load_yaml(ENV_DIR / f"{env_name}.yaml")
    if cfg:
        return cfg
    return _load_yaml(ENV_DIR / f"attached.{env_name}.yaml")


def _resolve_base_url(instance: str) -> str:
    """Derive the n8n REST base URL from a hostname or full URL."""
    instance = (instance or "").strip().rstrip("/")
    if not instance:
        raise RuntimeError("N8N_INSTANCE_NAME is empty")
    if instance.startswith(("http://", "https://")):
        return instance
    if "localhost" in instance or "127.0.0.1" in instance:
        return f"http://{instance}"
    return f"https://{instance}"


# ---------------------------------------------------------------------------
# N8nClient + cache
# ---------------------------------------------------------------------------

class N8nClient:
    """Minimal n8n REST client. Read, edit, extend."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        # Lazy import keeps `--help` working before deps install.
        import requests
        self._session = requests.Session()
        self._session.headers.update({
            "X-N8N-API-KEY": api_key,
            "Accept": "application/json",
        })

    def _url(self, path: str) -> str:
        path = path.lstrip("/")
        return f"{self.base_url}/{path}"

    def request(self, method: str, path: str, **kw):
        return self._session.request(method, self._url(path), timeout=30, **kw)

    def get(self, path: str, **kw):
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw):
        return self.request("POST", path, **kw)

    def put(self, path: str, **kw):
        return self.request("PUT", path, **kw)

    def delete(self, path: str, **kw):
        return self.request("DELETE", path, **kw)


# Cache keyed on (base_url, api_key_hash, env_name) and invalidated on
# .env / .env.<env> mtime changes so credential rotation is picked up.
_client_cache: Dict[Tuple[str, str, str], Tuple[N8nClient, float]] = {}


def _env_files_mtime(env_name: str) -> float:
    paths = [
        REPO_ROOT / ".env",
        REPO_ROOT / f".env.{env_name}",
        REPO_ROOT / f".env.attached.{env_name}",
        ENV_DIR / f"{env_name}.yaml",
        ENV_DIR / f"attached.{env_name}.yaml",
    ]
    return max((p.stat().st_mtime for p in paths if p.exists()), default=0.0)


def ensure_client(env_name: str) -> N8nClient:
    """Cached N8nClient for `env_name`. Re-reads .env if it changed."""
    snap = _load_env(env_name)
    api_key = snap.get("N8N_API_KEY") or os.environ.get("N8N_API_KEY", "")
    instance = snap.get("N8N_INSTANCE_NAME") or os.environ.get("N8N_INSTANCE_NAME", "")
    if not api_key:
        raise RuntimeError(
            f"N8N_API_KEY missing for env '{env_name}'. Set it in .env or .env.{env_name}."
        )
    if not instance:
        raise RuntimeError(
            f"N8N_INSTANCE_NAME missing for env '{env_name}'. Set it in .env, "
            f".env.{env_name}, or n8n/environments/{env_name}.yaml (n8n.instanceName)."
        )
    base_url = _resolve_base_url(instance)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:12]
    mtime = _env_files_mtime(env_name)
    cached = _client_cache.get((base_url, key_hash, env_name))
    if cached and cached[1] >= mtime:
        return cached[0]
    client = N8nClient(base_url, api_key)
    _client_cache[(base_url, key_hash, env_name)] = (client, mtime)
    return client


def restart_client(env_name: Optional[str] = None) -> None:
    """Drop cached N8nClient(s). `--reload` calls this."""
    if env_name is None:
        _client_cache.clear()
        return
    for k in list(_client_cache):
        if k[2] == env_name:
            _client_cache.pop(k, None)


def list_envs() -> List[str]:
    """Available env names from n8n/environments/*.yaml (excluding attached.*)."""
    if not ENV_DIR.exists():
        return []
    out = []
    for p in sorted(ENV_DIR.glob("*.yaml")):
        if p.stem.startswith("attached."):
            continue
        out.append(p.stem)
    return out


def default_env() -> str:
    """Pick the env: --env > N8H_ENV > 'dev' fallback if 'dev' YAML exists."""
    envs = list_envs()
    fallback = "dev" if "dev" in envs else (envs[0] if envs else "dev")
    return os.environ.get("N8H_ENV", fallback)


# ---------------------------------------------------------------------------
# version + update banner
# ---------------------------------------------------------------------------

def _version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version
        try:
            return version("n8n-harness")
        except PackageNotFoundError:
            pass
    except Exception:
        pass
    # Fallback: read pyproject.toml for editable installs without metadata.
    try:
        py = (REPO_ROOT / "pyproject.toml").read_text()
        m = re.search(r'^version\s*=\s*"([^"]+)"', py, re.MULTILINE)
        if m:
            return m.group(1)
    except Exception:
        pass
    return "0.0.0"


def _repo_dir() -> Optional[Path]:
    return REPO_ROOT if (REPO_ROOT / ".git").is_dir() else None


def _install_mode() -> str:
    if _repo_dir():
        return "git"
    return "pypi" if _version() != "0.0.0" else "unknown"


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------

def _doctor_check_api(client: Optional[N8nClient]) -> Tuple[bool, str]:
    if client is None:
        return False, "no client (env vars missing)"
    try:
        r = client.get("/api/v1/workflows", params={"limit": 1})
        return r.status_code == 200, f"HTTP {r.status_code}"
    except Exception as e:
        return False, f"error: {e!s}"


def _doctor_check_mcp() -> Tuple[bool, str]:
    """Best-effort probe: n8n-mcp is reachable from the agent's runtime.

    Within an MCP-enabled coding agent the tool call is the only definitive check;
    here we only confirm that *something* claims n8n-mcp registration. We do not
    fail doctor if MCP is unreachable — REST-fallback validator covers it.
    """
    indicators = [
        os.environ.get("CLAUDE_PLUGINS"),
        os.environ.get("MCP_SERVERS"),
    ]
    if any(indicators):
        return True, "env hints n8n-mcp registration (best-effort)"
    return True, "MCP not detected; REST-fallback validator will run"


def run_doctor() -> int:
    """Read-only health check. Exit 0 iff every must-pass row is `ok`.

    Status semantics (3-state):
      - "ok"   — green, must-pass rows are required to be in this state
      - "fail" — red, must-pass row failure → doctor exits 1
      - "warn" — yellow, advisory; never fails doctor on its own
                 (e.g. workflow IDs still placeholders before bootstrap)
    """
    print("n8n-harness doctor")
    print(f"  version           {_version()} ({_install_mode()})")
    print(f"  python            {sys.version.split()[0]}")

    env_name = default_env()
    print(f"  env               {env_name}")

    snap = _load_env(env_name)
    have_api = bool(snap.get("N8N_API_KEY") or os.environ.get("N8N_API_KEY"))
    have_inst = bool(snap.get("N8N_INSTANCE_NAME") or os.environ.get("N8N_INSTANCE_NAME"))
    have_orouter = bool(snap.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_KEY"))

    # rows: List[Tuple[label, status, detail]] where status ∈ {"ok", "fail", "warn"}
    rows: List[Tuple[str, str, str]] = []
    rows.append(("N8N_API_KEY", "ok" if have_api else "fail", "" if have_api else "missing — set in .env or .env.<env>"))
    rows.append(("N8N_INSTANCE_NAME", "ok" if have_inst else "fail", "" if have_inst else "missing — set in .env or YAML n8n.instanceName"))
    rows.append(("OPENROUTER_API_KEY", "ok" if have_orouter else "fail", "" if have_orouter else "missing — needed for helpers.llm()"))

    # pyyaml installed
    try:
        import yaml  # noqa: F401
        rows.append(("pyyaml", "ok", ""))
    except ImportError:
        rows.append(("pyyaml", "fail", "pip install pyyaml"))

    # All YAMLs parse
    yaml_ok = True
    for env in list_envs():
        try:
            _load_yaml(ENV_DIR / f"{env}.yaml")
        except Exception as e:
            yaml_ok = False
            rows.append((f"YAML parse: {env}", "fail", str(e)))
    if yaml_ok:
        rows.append(("environments YAML", "ok", f"{len(list_envs())} parsed"))

    # All .template.json parse
    tpl_ok = True
    tpl_dir = REPO_ROOT / "n8n" / "workflows"
    tpl_count = 0
    for tpl in tpl_dir.glob("*.template.json"):
        tpl_count += 1
        try:
            json.loads(tpl.read_text())
        except Exception as e:
            tpl_ok = False
            rows.append((f"template parse: {tpl.name}", "fail", str(e)))
    rows.append(("templates parse", "ok" if tpl_ok else "fail", f"{tpl_count} parsed"))

    # workflows.<key>.id non-placeholder check — WARN (not FAIL): a fresh clone
    # before bootstrap is supposed to have placeholder IDs.
    cfg = _yaml_for(env_name)
    placeholder_ids = []
    for k, v in (cfg.get("workflows") or {}).items():
        wid = str((v or {}).get("id", ""))
        if not wid or wid.startswith("your-") or wid in {"placeholder", "''", '""', "null"}:
            placeholder_ids.append(k)
    if placeholder_ids:
        rows.append((
            "workflow IDs", "warn",
            f"{len(placeholder_ids)} placeholder(s): {', '.join(placeholder_ids[:5])}"
            f"{' …' if len(placeholder_ids) > 5 else ''} — run `n8n-harness -c \"bootstrap()\"` to mint",
        ))
    else:
        rows.append(("workflow IDs", "ok", "all real"))

    # API reachable
    client = None
    if have_api and have_inst:
        try:
            client = ensure_client(env_name)
        except Exception as e:
            rows.append(("client", "fail", str(e)))
    api_ok, api_detail = _doctor_check_api(client)
    rows.append(("API reachable", "ok" if api_ok else "fail", api_detail))

    # MCP probe (informational — WARN, not fail)
    mcp_ok, mcp_detail = _doctor_check_mcp()
    rows.append(("n8n-mcp", "ok" if mcp_ok else "warn", mcp_detail))

    # Docker (optional, for start_local_n8n) — WARN if missing
    have_docker = bool(shutil.which("docker"))
    rows.append((
        "docker (optional)",
        "ok" if have_docker else "warn",
        "available" if have_docker else "not available — start_local_n8n() unavailable",
    ))

    # cloud_functions URL (optional) — WARN if unreachable, OK if not configured
    cf_url = ((cfg.get("cloudFunction") or {}).get("apiUrl") or "").strip()
    if cf_url and not cf_url.startswith("https://your-"):
        try:
            import requests as _req
            r = _req.get(cf_url, timeout=5)
            rows.append((
                "cloud_functions",
                "ok" if r.status_code < 500 else "warn",
                f"HTTP {r.status_code}",
            ))
        except Exception as e:
            rows.append(("cloud_functions", "warn", f"unreachable: {e}"))
    else:
        rows.append(("cloud_functions", "ok", "not configured (skipped)"))

    # Print rows with 3-state markers
    _MARK = {"ok": "ok  ", "fail": "FAIL", "warn": "WARN"}
    for label, status, detail in rows:
        mark = _MARK.get(status, "?")
        suffix = f" — {detail}" if detail else ""
        print(f"  [{mark}] {label}{suffix}")

    print("  .env-reading sites:")
    for site in ENV_READING_SITES:
        print(f"    - {site}")

    # Exit policy: any "fail" row → exit 1. "warn" never trips exit code.
    failures = [label for label, status, _ in rows if status == "fail"]
    return 0 if not failures else 1


# ---------------------------------------------------------------------------
# setup / update / reload (Phase 1b)
# ---------------------------------------------------------------------------

def _read_root_env_keys() -> Dict[str, str]:
    return _parse_dotenv(REPO_ROOT / ".env")


def _write_root_env(updates: Dict[str, str]) -> None:
    """Write updates into root .env, preserving existing ordering and comments."""
    path = REPO_ROOT / ".env"
    existing_lines = path.read_text().splitlines() if path.exists() else []
    have: Dict[str, int] = {}
    for i, line in enumerate(existing_lines):
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            have[s.split("=", 1)[0].strip()] = i
    for k, v in updates.items():
        new_line = f"{k}={v}"
        if k in have:
            existing_lines[have[k]] = new_line
        else:
            existing_lines.append(new_line)
    path.write_text("\n".join(existing_lines).rstrip() + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _prompt(label: str, default: Optional[str] = None, secret: bool = False) -> str:
    if secret:
        # Show masked default if one exists (never echo full secret).
        masked = ""
        if default:
            tail = default[-4:] if len(default) > 4 else "*"
            masked = f" [keep current ****{tail}]"
        import getpass
        try:
            v = getpass.getpass(f"{label}{masked}: ")
        except Exception:
            v = input(f"{label}{masked}: ")
    else:
        suffix = f" [{default}]" if default else ""
        v = input(f"{label}{suffix}: ")
    return (v.strip() or (default or ""))


def run_setup() -> int:
    """Interactive: write/update root .env, validate via GET /api/v1/workflows."""
    print("n8n-harness --setup: configuring root .env")
    if sys.version_info < (3, 11):
        print("error: python >= 3.11 required", file=sys.stderr)
        return 1
    try:
        import yaml  # noqa: F401
    except ImportError:
        print("error: pyyaml not installed; run `uv tool install -e .` again", file=sys.stderr)
        return 1

    cur = _read_root_env_keys()
    instance = _prompt("N8N_INSTANCE_NAME", default=cur.get("N8N_INSTANCE_NAME"))
    if not instance:
        print("N8N_INSTANCE_NAME is required.", file=sys.stderr)
        return 1
    api_key = _prompt("N8N_API_KEY", default=cur.get("N8N_API_KEY"), secret=True)
    if not api_key:
        print("N8N_API_KEY is required.", file=sys.stderr)
        return 1
    orouter = _prompt(
        "OPENROUTER_API_KEY (optional — needed for helpers.llm())",
        default=cur.get("OPENROUTER_API_KEY"),
        secret=True,
    )

    updates = {"N8N_INSTANCE_NAME": instance, "N8N_API_KEY": api_key}
    if orouter:
        updates["OPENROUTER_API_KEY"] = orouter

    _write_root_env(updates)
    print(f"wrote {REPO_ROOT / '.env'}")

    # Validate via GET /api/v1/workflows
    try:
        os.environ["N8N_INSTANCE_NAME"] = instance
        os.environ["N8N_API_KEY"] = api_key
        client = ensure_client(default_env())
        r = client.get("/api/v1/workflows", params={"limit": 1})
        if r.status_code != 200:
            print(f"validation failed: HTTP {r.status_code}", file=sys.stderr)
            return 1
        print(f"validated: GET /api/v1/workflows → HTTP {r.status_code}")
        return 0
    except Exception as e:
        print(f"validation failed: {e}", file=sys.stderr)
        return 1


def run_update(yes: bool = False) -> int:
    """`git pull --ff-only` for editable installs; uv tool upgrade fallback."""
    cur = _version()
    print(f"n8n-harness --update: current {cur}")
    mode = _install_mode()
    if mode == "git":
        repo = _repo_dir()
        status = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True, text=True,
        )
        if status.returncode != 0:
            print(f"git status failed: {status.stderr.strip()}", file=sys.stderr)
            return 1
        if status.stdout.strip():
            print(f"refusing to update on dirty worktree: {repo}", file=sys.stderr)
            return 1
        r = subprocess.run(["git", "-C", str(repo), "pull", "--ff-only"])
        return r.returncode
    if mode == "pypi":
        r = subprocess.run(["uv", "tool", "upgrade", "n8n-harness"])
        if r.returncode != 0:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "n8n-harness"])
            return r.returncode
        return 0
    print("unknown install mode; cannot auto-update.", file=sys.stderr)
    return 1


_VERSION_CACHE = Path.home() / ".cache" / "n8n-harness" / "version.json"
_GH_RELEASES = "https://api.github.com/repos/mwamedacen/n8n-harness/releases/latest"
_BANNER_TTL = 24 * 3600


def print_update_banner() -> None:
    """Daily update banner. Cached for 24h. Silent on errors / when up to date.

    Hits `releases/latest` once per day, compares against installed `_version()`,
    prints a one-line stderr nudge if there's a newer tag. Cache lives at
    `~/.cache/n8n-harness/version.json`.

    Quietly returns when:
      - GitHub is unreachable
      - the cache is fresh and last-checked tag <= installed version
      - no releases have been tagged yet (`tag_name` empty)
    """
    try:
        cache = {}
        if _VERSION_CACHE.exists():
            try:
                cache = json.loads(_VERSION_CACHE.read_text())
            except (json.JSONDecodeError, OSError):
                cache = {}
        now = time.time()
        if cache.get("checked_at", 0) + _BANNER_TTL > now:
            tag = cache.get("tag", "")
        else:
            try:
                import urllib.request as _u
                req = _u.Request(_GH_RELEASES, headers={"Accept": "application/vnd.github+json"})
                resp = _u.urlopen(req, timeout=3)
                data = json.loads(resp.read())
                tag = (data.get("tag_name") or "").lstrip("v")
            except Exception:
                return  # Network / API failure — stay quiet.
            try:
                _VERSION_CACHE.parent.mkdir(parents=True, exist_ok=True)
                _VERSION_CACHE.write_text(json.dumps({"tag": tag, "checked_at": now}))
            except OSError:
                pass
        if not tag:
            return
        cur = _version()
        if _vtuple(tag) > _vtuple(cur):
            print(
                f"[n8n-harness] update available: {cur} -> {tag} "
                f"(run `n8n-harness --update -y`)",
                file=sys.stderr,
            )
    except Exception:
        return  # Banner must never break a real command.


def _vtuple(v: str) -> tuple:
    """Lenient semver tuple — non-numeric components sort as 0."""
    out = []
    for s in (v or "0").split("."):
        n = ""
        for ch in s:
            if ch.isdigit():
                n += ch
            else:
                break
        out.append(int(n) if n else 0)
    return tuple(out)


# ---------------------------------------------------------------------------
# debug-deploys redaction
# ---------------------------------------------------------------------------

_REDACT_KEY_RE = re.compile(r".*(_API_KEY|_TOKEN|_SECRET|_PASSWORD)$", re.IGNORECASE)
_REDACT_HEADERS = {"authorization", "x-n8n-api-key"}


def redact_for_debug(obj: Any) -> Any:
    """Recursively scrub secrets and PII from an object before writing to disk.

    Rules:
      - any dict key matching `*_API_KEY` / `*_TOKEN` / `*_SECRET` / `*_PASSWORD` → "<REDACTED>"
      - HTTP headers: `Authorization`, `X-N8N-API-KEY` → "<REDACTED>"
      - any `credentials.*` block → values "<REDACTED>" (id/name kept)
      - URL query strings: scrub `api_key=`, `token=`, etc.
      - n8n instance hostname: replaced with `<REDACTED-INSTANCE>`. Captured
        from `os.environ.get("N8N_INSTANCE_NAME")` at redaction time, applied
        as a substring scrub to all strings in the object.
    """
    instance = (os.environ.get("N8N_INSTANCE_NAME") or "").strip()
    return _redact(obj, instance_host=instance)


def _redact(obj: Any, instance_host: str = "") -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            kl = str(k)
            if kl.lower() in _REDACT_HEADERS or _REDACT_KEY_RE.match(kl):
                out[k] = "<REDACTED>"
            elif kl == "credentials":
                out[k] = _redact_credentials(v)
            else:
                out[k] = _redact(v, instance_host=instance_host)
        return out
    if isinstance(obj, list):
        return [_redact(x, instance_host=instance_host) for x in obj]
    if isinstance(obj, str):
        s = _redact_url(obj)
        if instance_host and instance_host in s:
            s = s.replace(instance_host, "<REDACTED-INSTANCE>")
        return s
    return obj


def _redact_credentials(v: Any) -> Any:
    if isinstance(v, dict):
        # Keep structure but scrub values that look like secrets.
        out = {}
        for k, sub in v.items():
            if isinstance(sub, dict):
                # n8n credentials.<credName> = {id, name} — id/name aren't secrets
                # but if any leaked key/data slips in, redact it.
                inner = {}
                for ik, iv in sub.items():
                    if ik in {"id", "name"}:
                        inner[ik] = iv
                    else:
                        inner[ik] = "<REDACTED>"
                out[k] = inner
            else:
                out[k] = "<REDACTED>"
        return out
    return "<REDACTED>"


def _redact_url(s: str) -> str:
    if "://" not in s:
        return s
    try:
        parts = urllib.parse.urlsplit(s)
    except Exception:
        return s
    if not parts.query:
        return s
    pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    redacted = []
    for k, v in pairs:
        if _REDACT_KEY_RE.match(k.upper()) or k.lower() in {"api_key", "apikey", "token", "secret", "password"}:
            redacted.append((k, "<REDACTED>"))
        else:
            redacted.append((k, v))
    return urllib.parse.urlunsplit((
        parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(redacted), parts.fragment
    ))


_DEBUG_COUNTER = {"n": 0}


def debug_deploy_path() -> Path:
    """`~/.cache/n8n-harness/debug/<pid>/deploy-<n>.json`, mode 0600."""
    base = Path(os.path.expanduser("~/.cache/n8n-harness/debug"))
    d = base / str(os.getpid())
    d.mkdir(parents=True, exist_ok=True)
    _DEBUG_COUNTER["n"] += 1
    return d / f"deploy-{_DEBUG_COUNTER['n']}.json"


def write_debug_artifact(record: Dict[str, Any]) -> Path:
    path = debug_deploy_path()
    path.write_text(json.dumps(redact_for_debug(record), indent=2))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path
