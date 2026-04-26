# Gmail: sending email

## Node types

- `n8n-nodes-base.gmail` — send / read / move / label
- `n8n-nodes-base.gmailTrigger` — receive new mail (polling-based)

## Credential block

```json
"credentials": {
  "gmailOAuth2": {
    "id": "{{HYDRATE:env:credentials.gmail.id}}",
    "name": "{{HYDRATE:env:credentials.gmail.name}}"
  }
}
```

YAML side:

```yaml
credentials:
  gmail:
    id: "your-credential-id"
    name: "dev_gmail"
```

## Send-email shape

```json
{
  "type": "n8n-nodes-base.gmail",
  "parameters": {
    "operation": "send",
    "subject": "Weekly report — {{ $json.weekStart }}",
    "message": "{{HYDRATE:html:common/templates/report_email.template.txt}}",
    "options": {
      "sendTo": "ops@example.com",
      "ccList": "",
      "bccList": ""
    }
  }
}
```

## Common quirks

- **HTML vs plain text.** The `message` field is HTML by default; use `<br>` not `\n` for line breaks. Set `options.contentType: "text/plain"` to switch.
- **From address must match the credential's account.** You cannot spoof `From:` in Gmail without delegated send permissions configured outside n8n.
- **Rate limits.** Gmail API has per-user-per-day quotas. If a workflow sends thousands of emails, switch to a transactional service (SendGrid, Postmark) — Gmail is for occasional sends.
- **Trigger node delay.** `gmailTrigger` polls every minute by default. New mail can take up to a minute to fire. For real-time, use a webhook + push API (which Gmail does not have) — n8n's polling is the practical option.

## Worked example

Many existing workflows in this repo's user instance use Gmail to send digest emails after a SharePoint Excel-read + LLM-summary pipeline. The Send Email node sits at the end of the chain; its `message` field hydrates from `common/templates/report_email.template.txt`.
