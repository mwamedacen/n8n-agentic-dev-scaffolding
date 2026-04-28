---
name: install
description: How to install n8n-harness as a skill package and what it expects on the host system.
---

# install

## Prerequisites

- Python ≥ 3.11 on PATH
- Pip-installable: `pyyaml`, `requests`, `python-dotenv`
- An n8n instance the agent can reach via REST + an API key with workflow + credential scopes

## Install (one-time)

### Skill mode (any agent runtime)

Clone into your agent's skills directory:

```bash
cd ~/.claude/skills   # or wherever your agent runtime reads skills from
git clone https://github.com/<user>/n8n-harness.git
```

Install Python deps:

```bash
pip install pyyaml requests python-dotenv
```

(Optional, only if you'll use `iterate-prompt`:)

```bash
pip install dspy litellm
```

### Plugin mode (Claude Code only)

CLI form (run in your terminal):

```bash
claude plugin install https://github.com/mwamedacen/n8n-harness
```

In-session form (inside a Claude Code session):

```
/plugin install https://github.com/mwamedacen/n8n-harness
```

Local dev (loads from a local checkout):

```bash
claude --plugin-dir ./n8n-harness
```

#### Plugin extras

When installed as a plugin, n8n-harness ships two additional behaviors:

- **Slash commands** — 10 user-facing commands available as `/n8n-harness:deploy`, `/n8n-harness:tidyup`, etc. Hidden lifecycle skills remain agent-loadable via `SKILL.md` routing but do not appear in `/help`.

- **Auto-tidy hook** — a `PostToolUse` hook fires `tidy_workflow.py --in-place` automatically after every `*.template.json` Write/Edit/MultiEdit. This keeps node positions clean without any manual step.

  To disable the auto-tidy hook: remove or rename `hooks/hooks.json` in the plugin directory, or disable the plugin in Claude Code settings. Standalone-skill-mode users who want auto-tidy can configure the hook manually in `~/.claude/settings.json`.

## What the harness expects on disk

The skill package is a directory containing:

- `SKILL.md` — entry point
- `skills/*.md` and `skills/{patterns,integrations}/...md` — sub-skills
- `helpers/*.py` — the executable surface
- `primitives/` — seed templates copied into workspaces on demand

Helpers are invoked by absolute path (no console script, no PATH pollution):

```bash
python3 <harness>/helpers/<name>.py [args]
```

## Per-project setup

Per project, the agent runs `init.md` once to scaffold a workspace at `${PWD}/n8n-harness-workspace/`. From there, `bootstrap-env.md` configures envs, `create-new-workflow.md` authors workflows, etc. See [`SKILL.md`](SKILL.md) for the full skill catalogue.

## Updating

The harness's "version" is its git SHA. To upgrade:

```bash
cd ~/.claude/skills/n8n-harness
git pull
```

Breaking changes between versions are documented in [`CHANGELOG.md`](CHANGELOG.md). For the migration from the legacy single-repo shape (pre-`d6848fd`), see [`docs/migration-from-d6848fd.md`](docs/migration-from-d6848fd.md).

## Verifying the install

```bash
python3 <harness>/helpers/init.py --workspace /tmp/n8n-harness-smoke
ls /tmp/n8n-harness-smoke/n8n-config /tmp/n8n-harness-smoke/n8n-workflows-template
```

If both directories exist after the run, the install is good.
