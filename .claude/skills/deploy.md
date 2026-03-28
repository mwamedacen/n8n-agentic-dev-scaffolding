---
description: Deploy n8n workflows to an environment. Usage: /deploy dev, /deploy prod, /deploy dev periodic_excel_report
---

Deploy n8n workflows to the specified environment.

Parse "$ARGUMENTS" to extract:
- First word: environment name (e.g., "dev", "prod")
- Second word (optional): specific workflow key (e.g., "periodic_excel_report")
- Flags: "--keep-active" or "-k" to skip dev auto-deactivation

If a specific workflow key is provided, deploy just that workflow:
```bash
n8n/deployment_scripts/deploy_workflow.sh <env> <workflow_key>
```

If no workflow key is provided, deploy all workflows (tier-ordered):
```bash
n8n/deployment_scripts/deploy_all.sh <env>
```

If the user says "keep active" or passes -k, add the flag:
```bash
n8n/deployment_scripts/deploy_all.sh <env> --keep-active
```

After deployment, report the result (success/failure count).
