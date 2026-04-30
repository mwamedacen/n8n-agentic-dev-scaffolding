---
id: manage-variables-crud
category: bootstrap
difficulty: easy
---

# Configure n8n variables via the harness

## Prompt

> "Set up an n8n variable called `INVOICE_RETRY_LIMIT` with value `5` on the dev env. Then list what's there. Then delete a stale one called `OLD_FLAG`."

## Expected skills consulted

1. `skills/manage-credentials.md` (mentions variables in passing) or via `--help` discovery.

## Expected helpers invoked

1. `helpers/manage_variables.py create --env dev --name INVOICE_RETRY_LIMIT --value 5`
2. `helpers/manage_variables.py list --env dev` (with optional `--key INVOICE_RETRY_LIMIT` grep)
3. `helpers/manage_variables.py delete --env dev --id <looked-up-id> --force`

## Expected artifacts

None local — n8n variables are server-side state, not workspace state. The helper prints a NOTE to that effect.

## Expected state changes

- `INVOICE_RETRY_LIMIT=5` created on the n8n instance.
- `OLD_FLAG` removed from the instance after the agent looks up its id via `list` and passes to `delete --force`.

## Success criteria

- [ ] Subsequent `list` shows `INVOICE_RETRY_LIMIT` present and `OLD_FLAG` absent.
- [ ] No `JSONDecodeError` on create / delete. The helper handles n8n's empty 201/204 responses gracefully (post-task #9 fix).

## Pitfalls

- `create` and `delete` against `/api/v1/variables` return empty bodies on success (201/204). Pre-task-9, the helper crashed parsing those. Fixed in `n8n_client.py` — all 4 verbs now return `None` on empty `resp.content`.
- Agent must look up the id before calling `delete` — the helper takes `--id`, not `--name`.
- `delete` requires `--force` to actually issue the DELETE. Without it, the helper exits 0 with a confirmation prompt only.
