---
id: add-second-fn
category: cloud-functions
difficulty: easy
---

# Add a second function to an existing cloud-functions service

## Prompt

> "Add another cloud function — `extract_pdf_text` — to my existing service. Same Railway deployment."

## Expected skills consulted

1. `skills/add-cloud-function.md`

## Expected helpers invoked

1. `helpers/add_cloud_function.py --name extract_pdf_text --platform railway`

## Expected artifacts

- New file `cloud-functions/functions/extract_pdf_text.py` (agent fills body).
- `cloud-functions/registry.py` updated with the new import + `EXPOSED_FUNCTIONS["extract_pdf_text"]` entry.
- `cloud-functions-tests/test_extract_pdf_text.py` smoke stub.
- Existing `app.py` / `requirements.txt` / platform configs untouched (helper detects existing scaffold).

## Expected state changes

None. The user runs `railway up` after the function is implemented.

## Success criteria

- [ ] `cloud-functions/registry.py` lists both `resize_image` (from prior scenario) and `extract_pdf_text`.
- [ ] `pytest cloud-functions-tests/` collects and runs both tests cleanly.
- [ ] `app.py` un-modified — helper is purely additive on second-invocation.

## Pitfalls

- Same `--platform` value as the original. If the user wants to migrate from railway to supabase, that's a separate scaffolding task (they'd typically delete the workspace's `cloud-functions/` and re-init).
- `requirements.txt` doesn't auto-update — the agent must add new deps (e.g. `pdfplumber`, `pypdf2`) to the file by hand.

## Notes

The cloud-functions service is monorepo-style: one Railway service, one `app.py`, multiple functions exposed via `registry.py`. Calls from n8n are HTTP Request → `https://<service>.railway.app/<function-name>` with the JSON payload.
