---
name: tidy-workflow
description: Apply n8n's canvas-layout algorithm to a workflow template so node positions are clean and consistent.
---

# tidy-workflow

## When

After authoring or editing a workflow template — especially after `add-lock-to-workflow.md`, `add-rate-limit-to-workflow.md`, or any operation that shifts node positions. Also useful before committing templates to version control.

## How

```bash
python3 <harness>/helpers/tidy_workflow.py \
  --workspace <ws> \
  --workflow-key <key> \
  [--in-place]
```

- Default: prints the tidied JSON to stdout.
- `--in-place`: writes the result back to `<ws>/n8n-workflows-template/<key>.template.json`.

## Side effects

On first run, auto-installs `@n8n/workflow-sdk@stable` into `helpers/node_modules/` (~15–30 MB transitive, one-time cost). If `node`/`npm` are unavailable or the install fails, the helper falls back to a pure-Python BFS layout — less faithful than dagre but idempotent and crash-free.

Sticky notes (`type: n8n-nodes-base.stickyNote`) are never moved.

## Idempotence

Running tidy twice on the same input produces byte-identical output.

## Auto-tidy hook (plugin mode only)

When n8n-harness is installed as a Claude Code plugin, a PostToolUse hook fires `tidy_workflow.py --in-place` automatically after every `*.template.json` Write/Edit/MultiEdit. Standalone-skill-mode users who want auto-tidy can configure a hook manually in `~/.claude/settings.json`.

To disable the hook after plugin install: remove or rename `hooks/hooks.json` in the plugin directory, or disable the plugin in Claude Code settings.

## License

`@n8n/workflow-sdk` is published under the **n8n Sustainable Use License (SUL)**, not MIT. n8n-harness does not redistribute the SDK — your machine fetches it from npm at first run. By running this skill you accept the SUL terms for your use of the SDK. n8n-harness itself remains MIT.

## Install size

First run pulls `@n8n/workflow-sdk@stable` and its transitive dependencies (~15–30 MB). Subsequent runs skip the install check once `helpers/node_modules/@n8n/workflow-sdk` exists.

## See also

- `create-new-workflow.md` — scaffold a new workflow (tidy after editing)
- `add-lock-to-workflow.md` — adds nodes that shift positions (run tidy after)
- `add-rate-limit-to-workflow.md` — same
