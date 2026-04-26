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
