---
id: py-function-via-placeholder
category: authoring
difficulty: medium
---

# Python Code node with `{{@:py:...}}` (post-Pyodide caveat)

## Prompt

> "I want a Python Code node in my `text_classifier` workflow that does some lightweight string processing. Just stdlib stuff — no PIL, no pandas."

## Expected skills consulted

1. `skills/patterns/code-node-discipline.md` (Python section)

## Expected helpers invoked

1. (agent edits the template to add a Code node with `language: "python"`)
2. `helpers/test_functions.py --target n8n` (runs `pytest` over `n8n-functions-tests/test_*.py`)
3. `helpers/validate.py --workflow-key text_classifier`

## Expected artifacts

- `n8n-functions/py/normalize_label.py` — pure functions only, no top-level statements.
- `n8n-functions-tests/test_normalize_label.py` — pytest-style.
- Code node body referencing `{{@:py:n8n-functions/py/normalize_label.py}}`.

## Expected state changes

None until deploy.

## Success criteria

- [ ] `pytest n8n-functions-tests/test_normalize_label.py` passes in isolation.
- [ ] Validator clean.
- [ ] After deploy, the Python Code node executes correctly under n8n's runtime.

## Pitfalls

- **n8n Cloud post-Pyodide-removal caveat**: as of CVE-2025-68668 fallout, n8n removed Pyodide. On n8n Cloud, Python Code nodes lost capabilities — notably binary-file manipulation and arbitrary library imports. **For anything beyond stdlib string/dict/list manipulation on Cloud, defer to the cloud-functions FastAPI scaffold** (`skills/add-cloud-function.md`) and call it via HTTP Request from your workflow.
- Self-hosted n8n instances can install whatever Python packages they want in the Code-node container — the caveat is Cloud-specific.
- Naming: Python uses `snake_case`. File: `normalize_label.py`. Test: `test_normalize_label.py`.
- No `module.exports`-style trailer needed for Python. Test imports via the conftest-managed `sys.path`.
- The Python source file must NOT contain `# MATCH:py:`, `# /MATCH:py:`, `# DEHYDRATE:py:`, or `# /DEHYDRATE:py:` substrings — those are reserved round-trip markers and would corrupt resync.

## Notes

If the user actually needs PIL / pandas / heavy libs on n8n Cloud, the agent should say so explicitly and route to the cloud-function scenario instead of trying to make the Code node work.
