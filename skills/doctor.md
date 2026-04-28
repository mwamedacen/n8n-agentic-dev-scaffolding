---
name: doctor
description: Health check — workspace tree, env YAMLs, templates, n8n API reachability.
---

# doctor

## When

Anything goes wrong, or before an important deploy.

## How

```bash
python3 <harness>/helpers/doctor.py [--env <name>]
```

## Side effects

Prints a 3-state (✓/⚠/✗) report:

- workspace tree presence
- per-env YAML parses + workflow-IDs not placeholder
- per-env n8n API reachable
- every `*.template.json` parses

Exit 0 unless any `✗ fail` row.

## See also

- [`skills/patterns/agent-api-discipline.md`](patterns/agent-api-discipline.md) — verify `POST /audit` body and category-section shape via Context7 before relying on training-data recall (especially when `--with-audit` enabled).
