# LLM providers (OpenRouter and friends)

## Why this is a pattern, not an integration

OpenRouter is *not* an n8n node type — it's accessed through OpenAI-compatible LLM nodes (`@n8n/n8n-nodes-langchain.lmChatOpenAi`, `@n8n/n8n-nodes-langchain.lmChatOpenRouter`, etc.) by changing the base URL. Because `find_skills(workflow_key)` keys off node `type`, a folder like `integration-skills/openrouter/` would never match. So OpenRouter (and other LLM-routing services) live here in `pattern-skills/`.

## Default provider

n8n-harness defaults to OpenRouter — the user's `.env` ships `OPENROUTER_API_KEY`, and `factory/prompt_engineering/config.py` has `DEFAULT_PROVIDER = "openrouter"`.

## Helper-side

`helpers.llm()` calls OpenRouter via plain HTTP:

```python
r = llm("Reply with the single word: pong")
```

Default model is `openai/gpt-4o-mini`. Override with `model="anthropic/claude-sonnet-4.6"` etc. — any model OpenRouter exposes.

## n8n-side: structured output

Use the LangChain "Chat Model" node + a "Structured Output Parser" node. Reference the schema with `{{HYDRATE:json:common/prompts/<schema>.json}}`:

```json
{
  "type": "@n8n/n8n-nodes-langchain.outputParserStructured",
  "parameters": {
    "schema": "{{HYDRATE:json:common/prompts/data_summary_schema.json}}"
  }
}
```

The prompt itself comes from `{{HYDRATE:txt:common/prompts/<prompt>.txt}}`. Together: prompt + schema → typed structured output.

## Choosing a provider

| Use case | Suggested provider |
|---|---|
| Cost-sensitive, summary / extraction | OpenRouter → `openai/gpt-4o-mini` or `google/gemini-flash-1.5` |
| High accuracy, complex reasoning | OpenRouter → `anthropic/claude-sonnet-4.6` or `openai/gpt-4o` |
| In-flight DSPy optimization | OpenRouter (LiteLLM agnostic) |
| n8n self-hosted with local models | Direct OpenAI-compatible endpoint to your Ollama/vLLM |

## Provider-specific quirks

- **OpenRouter strict mode.** Some models on OpenRouter enforce JSON-only output strictly. If you see "model returned text outside JSON block" errors, drop temperature to 0 and use a model with proven structured-output support (`gpt-4o-mini`, `claude-sonnet-4.6`).
- **Anthropic models on OpenRouter** count system tokens differently from direct Anthropic API. Cost reports may surprise you.
- **Model strings differ.** OpenRouter uses `<vendor>/<model>` (e.g. `openai/gpt-4o-mini`). Direct providers use just `<model>`.

## Switching default in DSPy

`factory/prompt_engineering/config.py:DEFAULT_PROVIDER` is now `"openrouter"`. Override per-call:

```python
configure_lm(provider="anthropic", model="claude-sonnet-4.6")
```

Or via env: `DSPY_PROVIDER=anthropic DSPY_MODEL=claude-sonnet-4.6 python3 example_evaluate.py`.
