"""
Example: Optimize prompts with DSPy optimizers.

This script shows how to:
1. Load train/val datasets
2. Define the module to optimize
3. Run MIPROv2 or BootstrapFewShotWithRandomSearch
4. Save the optimized program
5. Optionally export improved instructions back to common/prompts/

The optimization loop:
  prompt in common/prompts/ -> DSPy optimize -> improved prompt -> hydrate -> deploy

Usage:
    python3 example_optimize.py
    python3 example_optimize.py --optimizer bootstrap
    python3 example_optimize.py --export  # save optimized prompt back to common/prompts/
"""
import dspy
import json
import argparse
from pathlib import Path
from config import configure_lm
from example_signature import DataSummarizer
from example_evaluate import load_dataset, summary_quality_metric

PROJECT_ROOT = Path(__file__).parent.parent.parent
PROMPTS_DIR = PROJECT_ROOT / "common" / "prompts"


def optimize_with_mipro(program, trainset, metric):
    """Optimize using MIPROv2 (instruction + few-shot optimization)."""
    print("Running MIPROv2 optimization...")
    print("  This may take several minutes depending on dataset size and model speed.")
    print()

    optimizer = dspy.MIPROv2(
        metric=metric,
        auto="light",  # light/medium/heavy
        num_threads=1,
    )

    optimized = optimizer.compile(
        program,
        trainset=trainset,
        max_bootstrapped_demos=2,
        max_labeled_demos=2,
    )

    return optimized


def optimize_with_bootstrap(program, trainset, valset, metric):
    """Optimize using BootstrapFewShotWithRandomSearch."""
    print("Running BootstrapFewShotWithRandomSearch optimization...")
    print()

    optimizer = dspy.BootstrapFewShotWithRandomSearch(
        metric=metric,
        max_bootstrapped_demos=2,
        num_candidate_programs=4,
        num_threads=1,
    )

    optimized = optimizer.compile(
        student=program,
        trainset=trainset,
        valset=valset,
    )

    return optimized


def export_optimized_prompt(optimized_program, output_filename: str = "data_summary_prompt_optimized.txt"):
    """
    Extract optimized instructions from the program and save to common/prompts/.

    This closes the loop: DSPy optimization -> improved prompt file -> hydrate -> deploy
    """
    output_path = PROMPTS_DIR / output_filename

    # Extract the optimized instructions from the program's predictors
    instructions = []
    for name, predictor in optimized_program.named_predictors():
        if hasattr(predictor, 'signature') and hasattr(predictor.signature, 'instructions'):
            instructions.append(f"# {name}\n{predictor.signature.instructions}")

    if not instructions:
        print("No optimized instructions found in the program.")
        return None

    prompt_text = "\n\n".join(instructions)

    output_path.write_text(prompt_text)
    print(f"Exported optimized prompt to: {output_path}")
    print(f"  To use in workflows, update your template to reference:")
    print(f"  {{{{HYDRATE:txt:common/prompts/{output_filename}}}}}")

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Optimize prompts with DSPy")
    parser.add_argument("--optimizer", choices=["mipro", "bootstrap"], default="mipro",
                        help="Optimizer to use (default: mipro)")
    parser.add_argument("--export", action="store_true",
                        help="Export optimized prompt back to common/prompts/")
    args = parser.parse_args()

    # Configure LM
    try:
        configure_lm()
    except ValueError as e:
        print(f"Error: {e}")
        print("An API key is required for optimization. Set it in your .env file.")
        return

    # Load dataset
    try:
        dataset = load_dataset("sample_dataset.json")
    except FileNotFoundError:
        print("No dataset found. Create datasets/sample_dataset.json first.")
        return

    if len(dataset) < 4:
        print(f"Need at least 4 examples for optimization, found {len(dataset)}")
        return

    # Split dataset
    split_idx = len(dataset) // 2
    trainset = dataset[:split_idx]
    valset = dataset[split_idx:]

    print(f"Train set: {len(trainset)} examples")
    print(f"Val set: {len(valset)} examples")
    print()

    # Create base program
    program = DataSummarizer()

    # Optimize
    if args.optimizer == "mipro":
        optimized = optimize_with_mipro(program, trainset, summary_quality_metric)
    else:
        optimized = optimize_with_bootstrap(program, trainset, valset, summary_quality_metric)

    print()
    print("Optimization complete!")

    # Evaluate optimized program
    print("\nEvaluating optimized program on validation set...")
    evaluator = dspy.Evaluate(
        devset=valset,
        metric=summary_quality_metric,
        num_threads=1,
    )
    score = evaluator(optimized)
    print(f"Optimized score: {float(score):.2%}")

    # Export if requested
    if args.export:
        print()
        export_optimized_prompt(optimized)


if __name__ == "__main__":
    main()
