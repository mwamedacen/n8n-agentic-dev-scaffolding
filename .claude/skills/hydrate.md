---
description: Hydrate n8n workflow templates for an environment without deploying. Usage: /hydrate dev, /hydrate prod periodic_excel_report
---

Hydrate (generate) n8n workflow templates for the specified environment without deploying.

Parse "$ARGUMENTS" to extract:
- First word: environment name (e.g., "dev", "prod")
- Second word (optional): specific workflow key (e.g., "periodic_excel_report")

If a specific workflow key is provided, hydrate just that workflow:
```bash
python3 n8n/build_scripts/hydrate_workflow.py -e <env> -t n8n/workflows/<workflow_key>.template.json -k <workflow_key>
```

If no workflow key is provided, hydrate all discovered templates:
```bash
python3 n8n/build_scripts/hydrate_all.py -e <env>
```

After hydration, report which workflows were generated and their output paths.
