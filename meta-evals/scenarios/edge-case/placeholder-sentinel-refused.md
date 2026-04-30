---
id: placeholder-sentinel-refused
category: edge-case
difficulty: medium
---

# Sentinel placeholder — hydrate refuses with clear remediation

## Prompt

> "Deploy `order_processing`. (User just ran bootstrap-env but skipped stage 3 — `pricing_calc.id` in dev.yml is still `placeholder`.)"

## Expected skills consulted

1. `skills/bootstrap-env.md`
2. `skills/deploy.md`

## Expected helpers invoked

1. `helpers/deploy.py --env dev --workflow-key order_processing` → calls hydrate internally → ValueError raised by env_resolver sentinel guard
2. (agent runs) `helpers/bootstrap_env.py --env dev` to mint real ids
3. `helpers/deploy.py --env dev --workflow-key order_processing` succeeds.

## Expected artifacts

After bootstrap-env: `dev.yml.workflows.pricing_calc.id` is now a real n8n id (was `'placeholder'` before).

## Expected state changes

After bootstrap: a fresh placeholder workflow is minted on n8n with the right id.

## Success criteria

- [ ] Hydrate fails with `ValueError: Sentinel value 'placeholder' resolved for {{@:env:workflows.pricing_calc.id}} in dev.yml. Run \`python3 <harness>/helpers/bootstrap_env.py --env dev\` to mint real IDs.`
- [ ] Agent reads the remediation and runs bootstrap-env, NOT some other workaround.
- [ ] After bootstrap, deploy succeeds.

## Pitfalls

- **Pre-task-9 behavior** (legacy bug): hydrate silently embedded the literal string `"placeholder"` into the deployed workflow JSON. Then dehydrate's reverse-substitution skipped `workflows.*` keys (correctly), so the corruption was irreversible — the next round-trip locked in the broken value.
- **Post-task-9 behavior** (current): hydrate raises ValueError BEFORE the build is written. Workspace state is preserved.
- The sentinel set is `{'', 'placeholder'}` plus any value starting with `'your-'`. If a user genuinely needs the literal string `'placeholder'` somewhere, they can't put it in `workflows.*` or `credentials.*` paths — those are guarded.
- The guard is scoped to `workflows.*` and `credentials.*` ONLY. Other env paths (`displayName`, `workflowNamePostfix`, etc.) can have the value `'placeholder'` legitimately.

## Notes

This was task-9 finding #2. Original tester diagnosis blamed dehydrate; falsification revealed it was hydrate's forward-pass. Fix lives in env_resolver, not dehydrate.
