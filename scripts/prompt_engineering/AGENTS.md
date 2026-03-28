# DSPy Prompt Engineering Framework

## Overview

This directory contains a DSPy-based prompt engineering framework for systematically evaluating and optimizing prompts used in the n8n-scaffolder-for-coding-agents project.

**DSPy** is a framework for algorithmically optimizing LM prompts and weights. Instead of manually tweaking prompts, DSPy lets you define what you want (via typed signatures and metrics) and automatically finds the best prompt formulation through optimization.

### Why DSPy?

- **Reproducible evaluation**: Define metrics once, run them consistently across prompt versions
- **Automatic optimization**: MIPROv2 and BootstrapFewShot find better instructions and few-shot examples automatically
- **Typed signatures**: Match your existing JSON schemas from `common/prompts/` with strongly-typed Python signatures
- **Provider-agnostic**: Supports OpenAI, Anthropic, OpenRouter, and any LiteLLM-compatible provider

## The Prompt Engineering Loop

```
common/prompts/*.txt  -->  DSPy Signature  -->  Evaluate (metrics)
        ^                                            |
        |                                            v
   hydrate + deploy  <--  Export optimized  <--  Optimize (MIPROv2)
```

1. **Define**: Create a DSPy `Signature` that mirrors your `common/prompts/` schema
2. **Evaluate**: Run `example_evaluate.py` against a dataset to measure current prompt quality
3. **Optimize**: Run `example_optimize.py` to find better instructions/few-shot examples
4. **Export**: Use `--export` flag to write the optimized prompt back to `common/prompts/`
5. **Deploy**: The hydrate system picks up the updated prompt file for workflow deployment

## Defining Signatures from JSON Schemas

Each prompt+schema pair in `common/prompts/` maps to a DSPy Signature:

```python
class DataSummary(dspy.Signature):
    """Generate a concise summary from structured data metrics."""

    # Input fields (from your workflow's input data)
    data_description: str = dspy.InputField(desc="Description of the data being summarized")
    metrics_json: str = dspy.InputField(desc="JSON string of computed metrics")

    # Output fields (matching your JSON schema's properties)
    summary: str = dspy.OutputField(desc="A 2-3 sentence summary of the data")
    highlights: list[str] = dspy.OutputField(desc="Key highlights or notable findings")
    top_category: Optional[str] = dspy.OutputField(desc="The top category by volume or amount")
```

The signature docstring becomes the base instruction. DSPy optimizers will refine this automatically.

## Building Evaluation Datasets

Datasets live in `datasets/` as JSON files. Each example has an `input` and `expected_output`:

```json
[
  {
    "input": {
      "data_description": "Monthly expense report across departments",
      "metrics": {
        "totalAmount": 45230.50,
        "rowCount": 156,
        "categories": { ... }
      }
    },
    "expected_output": {
      "summary": "The monthly expense report shows $45,230.50 in total...",
      "highlights": ["Operations accounts for over half of total spending", ...]
    }
  }
]
```

### Best Practices for Datasets

- **Minimum 6 examples** for meaningful evaluation, 20+ for optimization
- **Cover edge cases**: zero values, single categories, large numbers, missing fields
- **Include diverse scenarios**: different data types, scales, and domains
- **Keep expected outputs realistic**: they serve as ground truth for metrics
- **Split consistently**: Use first half for training, second half for validation

## Running Evaluation

```bash
cd scripts/prompt_engineering
pip install -r requirements.txt

# Run evaluation against sample dataset
python3 example_evaluate.py
```

The evaluator:
1. Loads examples from `datasets/sample_dataset.json`
2. Splits into dev/test sets
3. Runs the `DataSummarizer` module on each test example
4. Scores with `summary_quality_metric` (checks length, highlights, key numbers)
5. Reports overall score

### Custom Metrics

Two metric types are provided:

- **`summary_quality_metric`**: Rule-based, fast, no LLM calls. Checks summary length, highlight count, and whether key numbers appear in the output.
- **`llm_judge_metric`**: Uses an LLM to assess accuracy and quality. More expensive but more nuanced.

Metrics follow the DSPy convention:
- When `trace is not None` (during optimization): return `bool` (pass/fail threshold)
- When `trace is None` (during evaluation): return `float` (0.0 to 1.0 score)

## Running Optimization

```bash
# MIPROv2 optimization (default) - optimizes instructions + few-shot examples
python3 example_optimize.py

# BootstrapFewShot optimization - finds best few-shot examples
python3 example_optimize.py --optimizer bootstrap

# Optimize and export the improved prompt back to common/prompts/
python3 example_optimize.py --export
```

### MIPROv2

- Optimizes both the instruction text and few-shot demonstrations
- Uses `auto="light"` by default (fewer trials, faster). Change to `"medium"` or `"heavy"` for better results
- Best for improving instruction quality

### BootstrapFewShotWithRandomSearch

- Focuses on finding the best few-shot examples from your training data
- Generates `num_candidate_programs` variants and picks the best
- Best for tasks where examples matter more than instructions

## Exporting Optimized Prompts

After optimization, use `--export` to save the improved prompt:

```bash
python3 example_optimize.py --export
```

This writes to `common/prompts/data_summary_prompt_optimized.txt`. To use it in your workflows, update your template reference:

```
{{HYDRATE:txt:common/prompts/data_summary_prompt_optimized.txt}}
```

## Configuration

### Environment Variables

Set these in your project root `.env` or `.env.dev` file:

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `OPENROUTER_API_KEY` | OpenRouter API key | `sk-or-...` |
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-...` |
| `DSPY_PROVIDER` | Default provider | `openai`, `openrouter`, `anthropic` |
| `DSPY_MODEL` | Default model | `gpt-4o`, `claude-sonnet-4-20250514` |

### Provider Selection

```python
from config import configure_lm

# Use defaults from .env
configure_lm()

# Override provider and model
configure_lm(provider="openrouter", model="google/gemini-2.5-pro-preview")
configure_lm(provider="anthropic", model="claude-sonnet-4-20250514")
configure_lm(provider="openai", model="gpt-4o")

# Pass additional kwargs to dspy.LM
configure_lm(temperature=0.7, max_tokens=1000)
```

## Quick Commands Reference

```bash
# Setup
cd scripts/prompt_engineering
pip install -r requirements.txt

# Run signature demo (shows how to load prompts/schemas)
python3 example_signature.py

# Evaluate current prompt quality
python3 example_evaluate.py

# Optimize with MIPROv2
python3 example_optimize.py

# Optimize with BootstrapFewShot
python3 example_optimize.py --optimizer bootstrap

# Optimize and export back to common/prompts/
python3 example_optimize.py --export
```

## File Structure

```
scripts/prompt_engineering/
  requirements.txt          # Python dependencies
  config.py                 # LM provider configuration
  example_signature.py      # Signature definitions + demo
  example_evaluate.py       # Evaluation with custom metrics
  example_optimize.py       # Prompt optimization
  datasets/
    sample_dataset.json     # Sample evaluation dataset (6 examples)
  AGENTS.md                 # This file
```

## DSPy Documentation

Use the **Context7** MCP server to fetch up-to-date DSPy docs directly in your editor. Context7 is preferred over web search — DSPy's API evolves quickly and training data may be stale.

Static references (may be outdated):
- Official docs: https://dspy.ai/
- DSPy GitHub: https://github.com/stanfordnlp/dspy
- Signatures guide: https://dspy.ai/learn/programming/signatures/
- Optimizers guide: https://dspy.ai/learn/optimization/optimizers/
- Evaluation guide: https://dspy.ai/learn/evaluation/metrics/
