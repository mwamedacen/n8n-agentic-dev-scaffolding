---
id: dependency-graph-subworkflow
category: debug
difficulty: easy
---

# Map sub-workflow dependencies via dependency_graph

## Prompt

> "Show me which workflows call which sub-workflows on dev."

## Expected skills consulted

1. `skills/debug.md` (step 1)

## Expected helpers invoked

1. `helpers/dependency_graph.py --env dev` (default `--source both`)

## Expected artifacts

None — output is printed to stdout.

## Expected state changes

None.

## Success criteria

- [ ] Output contains three sections: `calls (Execute Workflow)`, `error_handlers`, `credential_groups`.
- [ ] Edges with `{{@:env:workflows.X.id}}` placeholders resolve to the workflow key X (post-task-9 default `--source both` includes live-side resolution for templates that haven't been hydrated yet).

## Pitfalls

- **Default `--source` is `both`**, NOT `template` only. Template-only mode misses live-side workflows that haven't been mirrored into the workspace and may show edges as raw env-placeholders. Use the default unless you have a reason to filter.
- The graph is flat — no recursive walk into sub-workflows of sub-workflows. For multi-level dependency analysis, run multiple times keying off interesting nodes.
- `error_handlers` section sources from BOTH `settings.errorWorkflow` in templates AND `n8n-config/common.yml.error_source_to_handler` for indirect-dispatch wiring. Mismatches between the two are signal — check that they agree.

## Notes

A common debug move: dep-graph BEFORE inspecting a failed execution, so you know which downstream workflows might also have been affected by an upstream credential rotation, missing variable, etc.
