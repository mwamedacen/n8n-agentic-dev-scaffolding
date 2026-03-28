---
description: Deactivate all n8n workflows for an environment. Usage: /deactivate dev, /deactivate prod
---

Deactivate all n8n workflows for the specified environment.

Parse "$ARGUMENTS" to extract:
- First word: environment name (e.g., "dev", "prod")

Run:
```bash
n8n/deployment_scripts/deactivate_all.sh <env>
```

Report the result (how many workflows were deactivated).
