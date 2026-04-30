---
id: scaffold-fastapi-fn
category: cloud-functions
difficulty: medium
---

# Scaffold a FastAPI cloud function for binary-file manipulation

## Prompt

> "I need to resize uploaded images before storing them. n8n Cloud's Python Code node can't import PIL since they removed Pyodide. Set up a cloud function I can call via HTTP."

## Expected skills consulted

1. `skills/add-cloud-function.md`
2. `skills/patterns/code-node-discipline.md` (for the related Code-node discipline)

## Expected helpers invoked

1. `helpers/add_cloud_function.py --name resize_image --platform railway`

## Expected artifacts

- `cloud-functions/app.py` (FastAPI scaffold, only on first invocation).
- `cloud-functions/registry.py` with `EXPOSED_FUNCTIONS` dict; the helper appends `resize_image` to it.
- `cloud-functions/functions/resize_image.py` — agent fills with the actual resize logic using PIL or similar.
- `cloud-functions/requirements.txt` — agent adds `pillow` here.
- `cloud-functions/{railway.toml, railpack.json}` — Railway platform config.
- `cloud-functions-tests/test_resize_image.py` — smoke test stub.

## Expected state changes

None on n8n; deployment to Railway is out of scope for the harness (user runs `railway up` themselves).

## Success criteria

- [ ] `pytest cloud-functions-tests/test_resize_image.py` passes (auto-seeded `conftest.py` puts `cloud-functions/` on `sys.path` so the import works).
- [ ] `cloud-functions/registry.py` has the new `from functions.resize_image import resize_image` line and an `EXPOSED_FUNCTIONS["resize_image"] = resize_image` entry.

## Pitfalls

- Cloud functions are the **escape hatch for Cloud-only capability gaps post-Pyodide-removal**. On self-hosted n8n, you can install Python deps in the Code-node container directly — the cloud-functions scaffold is unnecessary.
- `add_cloud_function.py` only seeds `app.py`/`registry.py`/`requirements.txt`/platform configs on first invocation. Subsequent calls add only the new function file + registry entry + test stub.
- `cloud-functions-tests/conftest.py` is auto-seeded by `init.py` (post-task-9 fix). If you're on an older harness version, you may need to add it manually — check that `pytest --target cloud` works.
- The actual function body is the agent's responsibility. The seed `hello_world.py` shows the input/output contract: takes a dict, returns a dict.
