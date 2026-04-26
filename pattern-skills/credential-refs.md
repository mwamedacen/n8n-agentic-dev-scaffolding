# Credential references in templates

## When to use

Whenever a node needs an authenticated provider (Microsoft Graph, Gmail, Redis, OpenRouter, …). n8n stores credentials in its encrypted DB; templates reference them by `id` AND `name`.

## Mechanics

In a node's `credentials` block, both `id` and `name` are required. Both come from `n8n/environments/<env>.yaml`:

```json
"credentials": {
  "microsoftGraphSecurityOAuth2Api": {
    "id": "{{HYDRATE:env:credentials.msOauth.id}}",
    "name": "{{HYDRATE:env:credentials.msOauth.name}}"
  }
}
```

YAML side:

```yaml
credentials:
  msOauth:
    id: "abc123-real-id"
    name: "dev_ms_oauth"
```

## The credential-`name`-mismatch trap

n8n verifies both fields on activate. If `id` is correct but `name` does not match the credential's actual name in the n8n UI, activation fails with a cryptic error like:

```
Credential not found
```

This happens silently on hydrate (it just substitutes the literal value); the failure surfaces later at deploy/activate.

**Fix:** make sure the YAML `name` matches the credential's name in the n8n UI exactly (case, whitespace, punctuation). If you renamed a credential in the UI, update the YAML.

## Resync behavior

`resync()` round-trips both fields back to `{{HYDRATE:env:credentials.<svc>.id}}` and `{{HYDRATE:env:credentials.<svc>.name}}` if your YAML has those values. If the YAML doesn't have an entry for the service yet, the literal id/name leak into the template — **add the credential entry to YAML before first resync**.

## Worked example

The existing Microsoft 365 nodes in `periodic_excel_report.template.json` all share `credentials.msOauth.{id,name}`. Adding a new MS Graph node needs nothing more than the same placeholder block — the YAML already has the entry.
