---
id: js-function-via-placeholder
category: authoring
difficulty: easy
---

# Workflow with a JS function injected via `{{@:js:...}}`

## Prompt

> "Add a Code node to my workflow `metrics_aggregator` that groups events by tenant and sums their cost. Make the logic testable in isolation."

## Expected skills consulted

1. `skills/patterns/code-node-discipline.md`

## Expected helpers invoked

1. (agent edits `n8n-workflows-template/metrics_aggregator.template.json`)
2. `helpers/test_functions.py --target n8n`
3. `helpers/validate.py --workflow-key metrics_aggregator`

## Expected artifacts

- `n8n-functions/js/groupCostByTenant.js`:
  ```js
  function groupCostByTenant(events) { /* pure */ }
  if (typeof module !== "undefined") module.exports = { groupCostByTenant };
  ```
- `n8n-functions-tests/groupCostByTenant.test.js` with `node:test` cases.
- Code node body in template:
  ```
  {{@:js:n8n-functions/js/groupCostByTenant.js}}
  const events = $input.all().map(i => i.json);
  return [{ json: { byTenant: groupCostByTenant(events) } }];
  ```

## Expected state changes

None until deploy.

## Success criteria

- [ ] `node --test n8n-functions-tests/groupCostByTenant.test.js` passes in isolation (no n8n runtime needed).
- [ ] Validator clean.
- [ ] After deploy, n8n executes the Code node identically to the unit test (round-trip markers wrap the function body in the deployed JS).

## Pitfalls

- Naming: JS uses `camelCase` for the function and the file. Test file matches: `<camelCaseName>.test.js`.
- The function file must contain ONLY function declarations — no top-level `$input.all()` or `return`. Those go in the Code-node body alongside the placeholder.
- The `module.exports` trailer is no-op in n8n's vm sandbox (where `module` is undefined) and active under `node --test`. Don't strip it "to clean up" — validator hard-fails without it.

## Notes

This is the workhorse pattern for any non-trivial Code-node logic. Once the function is extracted, n8n's UI hosts it via round-trip markers (`/* #:js:<path> */ ... /* /#:js:<path> */`); a later `resync` collapses the markers back to the placeholder so the template stays clean.
