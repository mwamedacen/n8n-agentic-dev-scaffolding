---
id: form-trigger-email
category: authoring
difficulty: easy
---

# Form Trigger → email send

## Prompt

> "I need a public form that takes a customer's email and a question, and sends a templated reply via Gmail. Key it as `support_intake`."

## Expected skills consulted

1. `skills/create-new-workflow.md`
2. `skills/integrations/gmail/sending-email.md`
3. `skills/manage-credentials.md`

## Expected helpers invoked

1. `helpers/create_workflow.py --key support_intake --name "Support Intake" --register-in dev`
2. (template: Form Trigger → Gmail Send)
3. `helpers/validate.py --workflow-key support_intake`
4. `helpers/deploy.py --env dev --workflow-key support_intake`

## Expected artifacts

- `n8n-workflows-template/support_intake.template.json` with `n8n-nodes-base.formTrigger` head.
- `n8n-assets/email-templates/support_intake_reply.html` with the templated body.
- The Gmail Send node references the HTML via `{{@:html:n8n-assets/email-templates/support_intake_reply.html}}`.

## Expected state changes

- Workflow deployed + activated. n8n exposes the form at the trigger's public URL.

## Success criteria

- [ ] Submitting the form (manually or via curl) produces a `success` execution.
- [ ] Recipient receives the templated email.

## Pitfalls

- Form Trigger has its own public URL (different from `/webhook/<path>`). Inspect via `get_workflow_details` after deploy or in the n8n UI.
- HTML email templates that include `<style>` or inline-CSS often interpolate variables — use `{{@:html:...}}` for the static structure and let the Gmail Send node substitute per-recipient fields via n8n expressions in the message body parameter.
- If the agent inlines a 5KB HTML blob into the template's `parameters.message`, validate.py won't reject it but `git diff` becomes unreadable. Discipline says: extract to `n8n-assets/email-templates/`.
