# Multi-env UUID collision

## Why this matters

n8n uses trigger node IDs (especially `webhookId`) to register webhook and schedule listeners. If two environments (dev and prod) on the **same n8n instance** share identical trigger IDs, they collide — one webhook overwrites the other, causing only one environment's workflow to fire.

Fresh UUIDs per environment prevent this. During hydration, every `{{HYDRATE:uuid:<name>}}` placeholder gets a fresh UUID v4. During resync, those UUIDs are replaced back with `{{HYDRATE:uuid:...}}` placeholders so templates stay portable.

## Where to use uuid placeholders

- **Webhook nodes:** both `id` and `webhookId` fields.
- **Schedule Trigger nodes:** the `id` field.
- **Manual Trigger nodes:** the `id` field.
- **Execute Workflow Trigger nodes:** the `id` field.
- **Chat Trigger nodes:** the `id` field.

Other nodes (Set, Code, Function, HTTP Request) do NOT need fresh UUIDs across envs — their internal IDs aren't externally registered.

## Hydration mechanics

```json
{
  "type": "n8n-nodes-base.webhook",
  "id": "{{HYDRATE:uuid:demo-webhook-id}}",
  "webhookId": "{{HYDRATE:uuid:demo-webhook-uuid}}",
  "parameters": { "path": "{{HYDRATE:uuid:demo-webhook-path}}" }
}
```

Each named placeholder resolves to a fresh UUID v4 per hydration. Within a single hydration, the same placeholder name resolves to the same UUID (so `id` and `webhookId` can share a name if you want them identical, or use distinct names if you want them different).

## Position recalculation rules

n8n does NOT auto-layout. When you add, remove, or reorder nodes, you MUST recalculate downstream positions:

- **Adding a node mid-flow:** shift all subsequent nodes right by 220px.
- **Removing a node:** shift subsequent nodes left by 220px to close the gap.
- **Adding a branch (If/Switch):** true branch at current Y, false at Y+200. Merge node at `max(true_x, false_x) + 220`.
- **Inserting before a branch:** shift the entire branch subtree (both paths) right.

Incorrect positions cause stacked / overlapping nodes in the n8n UI — readable workflows are part of the contract templates promise.

## Resync round-trip

The dehydrate step recognizes UUID v4 strings in the listed trigger fields and converts them back to placeholders. The placeholder name is auto-generated from the node's `name` (slugified to lowercase + dashes), so renaming a trigger node *after* it's deployed will create a fresh placeholder name on next resync — your existing template's old name disappears. To preserve naming, do the rename in the template first, then deploy.
