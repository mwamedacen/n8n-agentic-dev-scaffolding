---
description: Bootstrap placeholder workflows in n8n for a new or existing environment. Usage: /bootstrap-env dev, /bootstrap-env staging --dry-run
---

Create placeholder workflows in n8n for the specified environment and update the YAML config with new workflow IDs.

Parse "$ARGUMENTS" to extract:
- First word: environment name (e.g., "dev", "staging", "prod")
- Optional flag: "--dry-run" to preview without making API calls

If --dry-run is present:
```bash
python3 n8n/deployment_scripts/bootstrap_workflows.py <env> --dry-run
```

Otherwise:
```bash
python3 n8n/deployment_scripts/bootstrap_workflows.py <env>
```

After bootstrapping, suggest next steps:
1. Review updated YAML: `n8n/environments/<env>.yaml`
2. Hydrate: `python3 n8n/build_scripts/hydrate_all.py -e <env>`
3. Deploy: `n8n/deployment_scripts/deploy_all.sh <env>`
