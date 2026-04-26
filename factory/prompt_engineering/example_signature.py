"""
Example: Define DSPy signatures matching common/prompts/ schemas.

This script shows how to:
1. Define typed signatures that match your JSON schemas
2. Load prompt text from common/prompts/ as instructions
3. Use dspy.ChainOfThought for structured extraction
4. Run a sample extraction

Usage:
    python3 example_signature.py
"""
import dspy
import json
from pathlib import Path
from typing import Optional
from config import configure_lm

PROJECT_ROOT = Path(__file__).parent.parent.parent

# --- Signature matching data_summary_schema.json ---

class DataSummary(dspy.Signature):
    """Generate a concise summary from structured data metrics."""

    data_description: str = dspy.InputField(desc="Description of the data being summarized")
    metrics_json: str = dspy.InputField(desc="JSON string of computed metrics")

    summary: str = dspy.OutputField(desc="A 2-3 sentence summary of the data")
    highlights: list[str] = dspy.OutputField(desc="Key highlights or notable findings")
    top_category: Optional[str] = dspy.OutputField(desc="The top category by volume or amount")


# --- Module wrapping the signature ---

class DataSummarizer(dspy.Module):
    def __init__(self):
        self.summarize = dspy.ChainOfThought(DataSummary)

    def forward(self, data_description: str, metrics_json: str):
        return self.summarize(
            data_description=data_description,
            metrics_json=metrics_json
        )


# --- Load prompt from common/prompts/ ---

def load_prompt(prompt_filename: str) -> str:
    """Load a prompt text file from common/prompts/."""
    prompt_path = PROJECT_ROOT / "common" / "prompts" / prompt_filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")
    return prompt_path.read_text().strip()


def load_schema(schema_filename: str) -> dict:
    """Load a JSON schema from common/prompts/."""
    schema_path = PROJECT_ROOT / "common" / "prompts" / schema_filename
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    with open(schema_path) as f:
        return json.load(f)


# --- Demo ---

def main():
    # Configure LM (will use .env settings)
    try:
        configure_lm()
    except ValueError as e:
        print(f"Note: {e}")
        print("Running in demo mode (no actual LLM calls)")
        print()

    # Show loaded prompt and schema
    prompt = load_prompt("data_summary_prompt.txt")
    schema = load_schema("data_summary_schema.json")

    print("Loaded prompt:")
    print(f"  {prompt[:100]}...")
    print()
    print("Loaded schema fields:")
    for field, info in schema.get("schema", schema).get("properties", {}).items():
        print(f"  {field}: {info.get('type', 'unknown')} - {info.get('description', '')}")
    print()

    # Sample input
    sample_metrics = json.dumps({
        "totalAmount": 45230.50,
        "rowCount": 156,
        "avgAmount": 290.07,
        "categories": {
            "Operations": {"count": 82, "total": 24100.00},
            "Marketing": {"count": 45, "total": 13500.50},
            "IT": {"count": 29, "total": 7630.00}
        }
    })

    print("Sample input metrics:")
    print(f"  {sample_metrics[:100]}...")
    print()

    # Run the module (only if LM is configured)
    try:
        summarizer = DataSummarizer()
        result = summarizer(
            data_description="Monthly expense report across departments",
            metrics_json=sample_metrics
        )

        print("Result:")
        print(f"  Summary: {result.summary}")
        print(f"  Highlights: {result.highlights}")
        print(f"  Top Category: {result.top_category}")
    except Exception as e:
        print(f"Could not run LLM inference: {e}")
        print("This is expected if no API key is configured.")
        print("Set OPENAI_API_KEY or OPENROUTER_API_KEY in your .env file to run.")


if __name__ == "__main__":
    main()
