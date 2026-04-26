---
name: integration-slack
description: Slack nodes — bot/user OAuth, posting messages, threads.
---

# Slack

## Node type

`n8n-nodes-base.slack`.

## Credential type

`slackApi` (bot token) or `slackOAuth2Api` (full OAuth flow).

For setup, see [`skills/manage-credentials.md`](../../manage-credentials.md). Bot tokens (`slackApi`) are simpler — paste `xoxb-...` into `.env.<env>` and run Path A.

## Common operations

- **Post message:** `resource: message`, `operation: post`. Set `channel` to a channel ID (preferred) or `#name` (sometimes resolves slowly).
- **Reply in thread:** include `thread_ts` from a previous message.
- **Update message:** `operation: update` with `ts` of the original message.

## Channel ID gotcha

Slack's UI shows `#channel-name` but the API takes channel IDs (e.g. `C0123456789`). Find the ID by right-clicking the channel → Copy Link → the URL contains the ID. Store the ID in your env YAML, not the name:

```yaml
slack:
  alertsChannel: "C0123456789"
```

```json
{
  "type": "n8n-nodes-base.slack",
  "parameters": {
    "channel": "{{HYDRATE:env:slack.alertsChannel}}"
  }
}
```
