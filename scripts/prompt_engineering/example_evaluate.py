"""
Example: Evaluate prompt quality with DSPy metrics.

This script shows how to:
1. Load evaluation datasets as dspy.Example objects
2. Define custom metric functions (exact match, tolerance-based, LLM-as-judge)
3. Run dspy.Evaluate against a dataset
4. Report per-field and overall accuracy

Usage:
    python3 example_evaluate.py
"""
import dspy
import json
from pathlib import Path
from config import configure_lm
from example_signature import DataSummarizer

DATASETS_DIR = Path(__file__).parent / "datasets"


def load_dataset(filename: str) -> list:
    """Load evaluation dataset as list of dspy.Example objects."""
    dataset_path = DATASETS_DIR / filename
    with open(dataset_path) as f:
        raw_data = json.load(f)

    examples = []
    for item in raw_data:
        example = dspy.Example(
            data_description=item["input"]["data_description"],
            metrics_json=json.dumps(item["input"]["metrics"]),
            summary=item["expected_output"]["summary"],
            highlights=item["expected_output"]["highlights"],
        ).with_inputs("data_description", "metrics_json")
        examples.append(example)

    return examples


# --- Custom Metrics ---

def summary_quality_metric(example, prediction, trace=None):
    """
    Evaluate summary quality using multiple criteria:
    1. Summary is non-empty and reasonable length
    2. Highlights list is non-empty
    3. Key numbers from input appear in summary
    """
    score = 0.0

    # Check summary exists and has reasonable length
    if hasattr(prediction, 'summary') and prediction.summary:
        summary = prediction.summary
        if 20 < len(summary) < 500:
            score += 0.4
        elif len(summary) > 0:
            score += 0.2

    # Check highlights exist
    if hasattr(prediction, 'highlights') and prediction.highlights:
        if len(prediction.highlights) >= 2:
            score += 0.3
        else:
            score += 0.15

    # Check that key metrics are referenced
    try:
        metrics = json.loads(example.metrics_json)
        total = str(int(metrics.get("totalAmount", 0)))
        if total in (prediction.summary or ""):
            score += 0.3
    except (json.JSONDecodeError, AttributeError):
        pass

    if trace is not None:
        return score >= 0.7
    return score


class AssessQuality(dspy.Signature):
    """Assess whether a data summary accurately represents the source metrics."""

    source_metrics: str = dspy.InputField(desc="The original metrics JSON")
    generated_summary: str = dspy.InputField(desc="The generated summary text")

    is_accurate: bool = dspy.OutputField(desc="Whether the summary accurately reflects the data")
    quality_score: float = dspy.OutputField(desc="Quality score from 0.0 to 1.0")


def llm_judge_metric(example, prediction, trace=None):
    """Use an LLM to judge summary quality (more expensive but more accurate)."""
    try:
        judge = dspy.Predict(AssessQuality)
        assessment = judge(
            source_metrics=example.metrics_json,
            generated_summary=prediction.summary or ""
        )
        score = float(assessment.quality_score) if assessment.is_accurate else 0.0
    except Exception:
        score = 0.0

    if trace is not None:
        return score >= 0.7
    return score


def main():
    try:
        configure_lm()
    except ValueError as e:
        print(f"Note: {e}")
        print("Set an API key in .env to run evaluation with actual LLM calls.")
        print()

    # Load dataset
    try:
        dataset = load_dataset("sample_dataset.json")
        print(f"Loaded {len(dataset)} evaluation examples")
    except FileNotFoundError:
        print("No dataset found. Create datasets/sample_dataset.json first.")
        print("See the sample format in CLAUDE.md")
        return

    if len(dataset) < 2:
        print("Need at least 2 examples for evaluation")
        return

    # Split into dev/test
    split_idx = max(1, len(dataset) // 2)
    devset = dataset[:split_idx]
    testset = dataset[split_idx:]

    print(f"Dev set: {len(devset)} examples")
    print(f"Test set: {len(testset)} examples")
    print()

    # Run evaluation with simple metric
    print("Running evaluation with summary_quality_metric...")
    try:
        evaluator = dspy.Evaluate(
            devset=testset,
            metric=summary_quality_metric,
            num_threads=1,
            display_progress=True,
        )

        program = DataSummarizer()
        score = evaluator(program)

        print(f"\nOverall score: {float(score):.2%}")
    except Exception as e:
        print(f"Evaluation failed: {e}")
        print("This is expected if no API key is configured.")


if __name__ == "__main__":
    main()
