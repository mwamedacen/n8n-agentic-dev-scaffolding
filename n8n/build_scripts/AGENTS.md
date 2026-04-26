# n8n Build Scripts

## Hydration Pipeline

`hydrate_workflow.py` resolves placeholders in a fixed order. Order matters because later steps may depend on earlier output.

1. **File** (`txt`, `json`, `html`) — inline file contents.
2. **JS** (`js`) — inline JavaScript with DEHYDRATE marker support.
3. **ENV** (`env`) — resolve dot-notation values from the environment YAML.
4. **UUID** (`uuid`) — generate fresh UUIDs (named identifiers cache within a run).
5. **Name resolution** — set workflow name with the env postfix (e.g. `[DEV]`).
6. **Validation** — assert no unresolved `{{HYDRATE:...}}` patterns remain.

Generic placeholder syntax and rationale live in `n8n/workflows/AGENTS.md`. Per-env UUID rationale lives in `pattern-skills/multi-env-uuid-collision.md`.

## Scripts

### hydrate_workflow.py

Single-workflow hydrator. Public entry from helpers: `hydrate(key, env=None)`.

```bash
python3 hydrate_workflow.py -e dev -t n8n/workflows/<key>.template.json -k <key>
```

Output: `n8n/workflows/generated/<env>/<key>.generated.json` (gitignored).

### hydrate_all.py

Auto-discovers `*.template.json` files in `n8n/workflows/` and hydrates each.

```bash
python3 hydrate_all.py -e dev [-v]
```

The harness's Python helper surface deliberately omits `hydrate_all` — agents compose with `for k in list_workflows(): hydrate(k)`. The bash script keeps its role for non-agent ergonomics.

## Helper modules (one-line each)

- `env_config.py` — `load_env_config`, `get_config_value`, `list_available_environments`, `flatten_config`, `validate_config`. Phase 3: also resolves `attached.<env>.yaml` as a fallback when `<env>.yaml` is absent.
- `env_hydrator.py` — `resolve_env_placeholders`, `find_env_placeholders`, `validate_all_placeholders_resolvable`.
- `file_hydrator.py` — `resolve_file_placeholders` for `txt`/`json`/`html`. Used inside Code-node string values too.
- `js_hydrator.py` — `resolve_js_placeholders` + `// DEHYDRATE:START` / `// DEHYDRATE:END` markers.
- `uuid_hydrator.py` — `resolve_uuid_placeholders`, `dehydrate_trigger_uuids`, `dehydrate_uuids_from_template`.
- `hydrate_validator.py` — final pass; raises if any `{{HYDRATE:...}}` survived.

## When to regenerate

Re-run hydration when any of these change: prompt files, JSON schemas, common JS, HTML templates, env YAML values, or the template itself. `deploy()` auto-regenerates first; a standalone hydrate is only useful for inspection.

## Node positions

When modifying a template (adding/removing/reordering), recalculate downstream positions — n8n does NOT auto-layout. Full rules in `pattern-skills/multi-env-uuid-collision.md`.

## Adding a new workflow

1. Create `n8n/workflows/<key>.template.json`.
2. Add the workflow entry to each `n8n/environments/<env>.yaml` under `workflows:` (id starts as a placeholder; bootstrap fills it).
3. Add to `n8n/deployment_order.yaml` in the appropriate tier (callees before callers).
4. `n8n-harness -c "bootstrap()"` to mint the n8n-side IDs.
5. `n8n-harness -c "hydrate('<key>'); deploy('<key>', activate=True)"` to ship.
