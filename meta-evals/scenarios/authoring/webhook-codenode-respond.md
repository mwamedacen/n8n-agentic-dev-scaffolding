---
id: webhook-codenode-respond
category: authoring
difficulty: easy
---

# Webhook → JS Code → respond-to-webhook

## Prompt

> "Build a workflow keyed `greet_api`. POST to its webhook with `{name: 'Ada'}`, get back `{greeting: 'Hello, Ada'}`. Use a JS function for the greeting logic so I can unit-test it."

## Expected skills consulted

1. `skills/create-new-workflow.md`
2. `skills/patterns/code-node-discipline.md` (for the `{{@:js:...}}` placeholder + paired test convention)
3. `skills/validate.md` and `skills/deploy.md`

## Expected helpers invoked

1. `helpers/create_workflow.py --key greet_api --name "Greet API" --register-in dev`
2. (agent edits the template to add Webhook → Code → Respond, plus JS function file + test)
3. `helpers/test_functions.py --target n8n` (runs the paired test)
4. `helpers/validate.py --workflow-key greet_api --source template`
5. `helpers/deploy.py --env dev --workflow-key greet_api`

## Expected artifacts

- `n8n-workflows-template/greet_api.template.json` with three nodes (Webhook, Greet, Respond) and `responseMode: "responseNode"`.
- `n8n-functions/js/greet.js` with a pure `greet(name)` function and the mandatory `if (typeof module !== "undefined") module.exports = { greet };` trailer.
- `n8n-functions-tests/greet.test.js` with `node:test` cases.

## Expected state changes

- Workflow deployed and activated on dev's n8n instance.

## Success criteria

- [ ] `curl -X POST -d '{"name":"Ada"}' <webhook-url>` returns HTTP 200 with `{"greeting":"Hello, Ada"}`.
- [ ] `pytest`-style test runner (the n8n-target via `node --test`) passes for the JS function in isolation.
- [ ] `validate.py` clean.

## Pitfalls

- The `{{@:js:...}}` path must be relative to the workspace root: `{{@:js:n8n-functions/js/greet.js}}`, not `{{@:js:greet.js}}`. Validator catches the latter with a clear "file not found" error reporting the resolved path.
- Code-node body must keep n8n glue (`$input`, `return [{json: ...}]`) OUTSIDE the function file. Validator rejects top-level statements in the pure-function file.
- Without the `module.exports` trailer, validator hard-fails — the trailer is mandatory for the paired test to import the function.

## Notes

This is the canonical entry-point scenario — every scenario that uses Code nodes follows the same pattern. The discipline trades 3 extra files for testability and round-trip stability.
