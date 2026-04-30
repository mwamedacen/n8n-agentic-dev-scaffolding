---
id: dspy-optimize-prompt-vs-dataset
category: prompt-iteration
difficulty: hard
---

# Optimize an LLM prompt against a paired schema + dataset using DSPy

## Prompt

> "I have a prompt at `n8n-prompts/prompts/categorize_email.txt`, a paired schema at `n8n-prompts/schemas/categorize_email_schema.json`, and 50 labeled examples at `n8n-prompts/datasets/categorize_email.jsonl`. Optimize the prompt for accuracy against the dataset."

## Expected skills consulted

1. `skills/iterate-prompt.md`
2. `skills/patterns/prompt-and-schema-conventions.md`

## Expected helpers invoked

1. `helpers/iterate_prompt.py --workspace <ws> --key categorize_email --metric accuracy [--budget <n>]`

## Expected artifacts

- `n8n-prompts/evals/categorize_email_<timestamp>.md` — the run report (baseline vs optimized scores, exemplars, per-example correctness).
- `n8n-prompts/prompts/categorize_email.txt` may be updated with the optimized version (depending on `--apply` flag — confirm with user before clobbering).

## Expected state changes

None on the n8n instance. The optimization is purely prompt-iteration in the workspace.

## Success criteria

- [ ] Optimized prompt scores ≥ baseline on the same eval set.
- [ ] Eval report includes a sample of failure cases with predicted vs. expected labels for human review.

## Pitfalls

- DSPy needs an LLM provider. The harness reads `OPENROUTER_API_KEY` (or equivalent) from `.env.<env>`. If unset, the helper exits 1 with a clear message.
- Don't use `--apply` casually — it overwrites your committed prompt. Run without `--apply` first, review the report, THEN apply.
- The dataset file is `.jsonl` (one JSON object per line). The first line should match the schema's input shape; the schema's output shape is the supervision signal.
- Optimization budget (`--budget`) is the LLM-call cap. Default is conservative (~50 calls) to bound cost. Bump for harder tasks; expect linear cost scaling.

## Notes

This is an LLM-prompt-engineering loop — not an n8n-workflow loop. The optimized prompt eventually gets dropped into a workflow's Code node or HTTP Request body via `{{@:txt:n8n-prompts/prompts/categorize_email.txt}}`.
