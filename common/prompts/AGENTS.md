# Prompt Conventions

## File Naming

- **Prompts**: `*_prompt.txt` (e.g., `data_summary_prompt.txt`)
- **Schemas**: `*_schema.json` (e.g., `data_summary_schema.json`)

Prompt and schema files are paired by prefix. For example, `data_summary_prompt.txt` and `data_summary_schema.json` work together -- the prompt instructs the LLM what to do, and the schema defines the structured output format.

## How Prompts Are Hydrated

Prompts are embedded into n8n workflow templates using the `txt` placeholder type:

```
{{HYDRATE:txt:common/prompts/data_summary_prompt.txt}}
```

During hydration, this is replaced with the escaped file contents. The prompt text is typically placed in a Set node assignment that feeds into an AI/OpenAI node.

## How Schemas Are Hydrated

JSON schemas are embedded using the `json` placeholder type:

```
{{HYDRATE:json:common/prompts/data_summary_schema.json}}
```

The JSON file contents are stringified and injected. This is used for structured output (response_format) in OpenAI-compatible AI nodes.

## Schema Format

Schemas use the `json_schema` wrapper format expected by OpenAI's structured output API:

```json
{
  "type": "json_schema",
  "name": "schema_name",
  "schema": {
    "type": "object",
    "properties": {
      "summary": {
        "type": "string",
        "description": "A 2-3 sentence summary"
      },
      "highlights": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Key findings"
      }
    },
    "required": ["summary", "highlights"]
  },
  "strict": true
}
```

Key points:
- The outer wrapper has `type`, `name`, `schema`, and `strict` fields
- `strict: true` enforces that the LLM output matches the schema exactly
- The `name` field should be a short identifier (snake_case)
- Properties should include `description` fields for LLM guidance

## Prompt Testing Policy

Every prompt change should be evaluated before deployment:

1. Add test cases to evaluation datasets in `scripts/prompt_engineering/`
2. Run evaluation to measure prompt quality against expected outputs
3. Optionally run DSPy optimization to find better prompt variants
4. Deploy after validation: `cd n8n/deployment_scripts && ./deploy_all.sh dev`

See `scripts/prompt_engineering/` for the full DSPy optimization workflow, including:
- `example_signature.py` -- Define DSPy signatures matching your schemas
- `config.py` -- Configure LM providers (OpenAI, OpenRouter, Anthropic)
