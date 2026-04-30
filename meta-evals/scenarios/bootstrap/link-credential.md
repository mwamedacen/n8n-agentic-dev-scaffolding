---
id: link-credential
category: bootstrap
difficulty: easy
---

# Link an existing UI-created credential to the env YAML

## Prompt

> "I already created a Slack credential called 'evolI-slack-bot' in the n8n UI. Wire it into my dev env so workflows can reference it as `credentials.slack`."

## Expected skills consulted

1. `skills/manage-credentials.md`

## Expected helpers invoked

1. `helpers/manage_credentials.py list-link --env dev --key slack --type slackOAuth2Api --from-name "evolI-slack-bot"`

## Expected artifacts

- `n8n-config/dev.yml` gains a `credentials.slack` block with `id`, `name`, `type`.

## Expected state changes

None — `list-link` is read-only on the n8n instance (no credential creation, just lookup-and-write-to-YAML).

## Success criteria

- [ ] After the helper, workflows can reference the credential via `{{@:env:credentials.slack.id}}` and `{{@:env:credentials.slack.name}}` placeholders.
- [ ] Re-running with same `--key` is idempotent.

## Pitfalls

- If multiple credentials share the same `--type`, the helper requires `--from-name` to disambiguate. Without it, exit 1 with the candidate list — agent should re-invoke with the correct name.
- For a brand-new credential (not yet in the UI), use `manage_credentials.py create` instead. That POSTs `/credentials` and writes the new id back. The `--env-vars "fieldName=ENV_VAR"` mapping reads values from `.env.<env>` — agent must add the env vars there first.

## Notes

`list-link` and `create` write to the same `credentials.<key>` block. Use `list-link` when the credential exists; `create` when it doesn't.
