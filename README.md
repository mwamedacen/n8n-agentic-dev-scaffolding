# n8n-harness

A read-only **skill package** for authoring, deploying, and operating n8n workflows from code.

The package contains markdown sub-skills (instruction docs for an AI agent), Python helper scripts (the executable surface), and seed primitive templates (lock workflows, minimal scaffolds). It does **not** contain user project state — that lives in a separate workspace at `${PWD}/n8n-harness-workspace/`.

## Install

```bash
# Once, into your agent's skills directory
cd ~/.claude/skills   # or wherever your agent reads skills from
git clone https://github.com/<user>/n8n-harness.git

# Global Python deps (lightweight by default)
pip install pyyaml requests python-dotenv
# Optional, for prompt iteration:
pip install dspy litellm
```

See [`install.md`](install.md) for prerequisites and IDE-specific notes.

## Usage

Read [`SKILL.md`](SKILL.md) — it routes any n8n-related request to the right sub-skill.

A typical first session:

```bash
# Per project
cd /path/to/your/project
python3 ~/.claude/skills/n8n-harness/helpers/init.py
python3 ~/.claude/skills/n8n-harness/helpers/bootstrap_env.py \
  --env dev --instance acme.app.n8n.cloud --api-key <your-key>
python3 ~/.claude/skills/n8n-harness/helpers/doctor.py --env dev
```

After that, you author workflows via `create-new-workflow.md`, deploy via `deploy-single-workflow-in-env.md`, etc.

## Mental model

- The harness directory is **read-only** from the agent's perspective.
- The workspace at `${PWD}/n8n-harness-workspace/` holds all authored artifacts.
- Helpers under `helpers/<name>.py` are independently invokable; there's no master CLI.
- Skills under `skills/` are markdown docs telling the agent what to do and which helper to invoke.

## What's in here

```
n8n-harness/
  SKILL.md                  # router — first thing the agent reads
  install.md                # install + prerequisites
  CHANGELOG.md              # version history
  README.md                 # this file
  LICENSE
  pyproject.toml            # pyyaml, requests, python-dotenv (+ optional [dspy])
  requirements.txt
  skills/                   # markdown sub-skills
    init.md, bootstrap-env.md, create-new-workflow.md, ...
    patterns/               # reusable n8n authoring patterns
    integrations/           # per-service quirks
  helpers/                  # executable Python — the actual machinery
    init.py, bootstrap_env.py, hydrate.py, deploy.py, run.py, ...
    placeholder/            # placeholder resolution primitives
  primitives/               # seed templates copied into workspace on demand
    workflows/              # lock_acquisition, lock_release, _minimal, ...
    cloud-functions/        # FastAPI seeds
    prompts/                # example prompt + schema pair
  tests/                    # offline + gated_real
  docs/
    migration-from-d6848fd.md
```

## License

MIT. See `LICENSE`.
