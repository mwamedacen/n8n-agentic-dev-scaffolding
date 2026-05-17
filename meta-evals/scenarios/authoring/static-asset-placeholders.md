---
id: static-asset-placeholders
category: authoring
difficulty: easy
---

# Static-asset placeholders: md, html, json

## Prompt

> "My workflow `summarizer` needs three static assets: an LLM prompt template (markdown), an HTML email body, and a JSON response schema. Wire them in via the harness's placeholder system instead of inlining."

## Expected skills consulted

1. `SKILL.md` (placeholder-syntax table)
2. `skills/patterns/prompt-and-schema-conventions.md`

## Expected helpers invoked

1. (agent edits `n8n-workflows-template/summarizer.template.json` to add placeholders)
2. `helpers/validate.py --workflow-key summarizer`
3. `helpers/hydrate.py --env dev --workflow-key summarizer` (verify substitution)

## Expected artifacts

- `n8n-prompts/prompts/summarize.md` — markdown-formatted LLM prompt template.
- `n8n-assets/email-templates/summary.html` — HTML email body.
- `n8n-prompts/schemas/summary_schema.json` — JSON output schema.
- Template references:
  - `{{@md:n8n-prompts/prompts/summarize.md}}` in the OpenAI/AI Agent node's prompt parameter.
  - `{{@html:n8n-assets/email-templates/summary.html}}` in the Gmail Send node's message parameter.
  - `{{@json:n8n-prompts/schemas/summary_schema.json}}` in a Set or Function node that needs the schema as a string.

## Expected state changes

None until deploy.

## Success criteria

- [ ] Hydrated build (`n8n-build/<env>/summarizer.generated.json`) contains the inlined contents of all three files (with `{{@json:...}}` JSON-stringified into a string field).
- [ ] No residual `{{@...}}` placeholders in the built JSON.
- [ ] Round-trip via `resync` preserves the placeholders (round-trip markers around content).

## Pitfalls

- **Path semantics**: all placeholder paths are relative to the **workspace root**, not to a default `n8n-prompts/` or `n8n-assets/` prefix. Validator's "file not found" reports the resolved path — read it.
- The `{{@json:...}}` placeholder reads the file content and emits it as a JSON-stringified value (suitable for embedding in a JSON-string field). Don't try to use it where a JSON object is expected directly — it produces a string.
- Pick the placeholder type by intent: `{{@html:...}}` for structured HTML, `{{@md:...}}` for a markdown-formatted prompt (the common case), `{{@txt:...}}` for opaque plain text. All three resolve to raw content — the type is a hint to reviewers about what's inside.

## Notes

This pattern keeps templates diff-friendly. Inlining a 200-line prompt or HTML blob into a `*.template.json` makes every prompt-tweak look like a workflow-structure change in `git diff`.
