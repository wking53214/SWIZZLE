#!/usr/bin/env python3
"""Evaluate all corpus scenarios with independent oracles.

This script runs WIZZLE's evaluation pipeline on each scenario repository,
generating comprehensive epistemic assessments that determine whether
Ghost's conclusions are justified by the available evidence.
"""

import json
from pathlib import Path
from swizzle.wizzle.evaluator import Evaluator

def evaluate_scenarios():
    """Evaluate all scenario repositories."""
    corpus_dir = Path(__file__).parent / "corpus"

    print("=" * 70)
    print("WIZZLE Scenario Evaluation")
    print("=" * 70)

    scenarios = list(corpus_dir.glob("*/"))
    print(f"\nFound {len(scenarios)} scenario repositories")

    results = {}

    for scenario_path in sorted(scenarios):
        scenario_name = scenario_path.name
        print(f"\n{'=' * 70}")
        print(f"Evaluating: {scenario_name}")
        print(f"{'=' * 70}")

        # Initialize evaluator
        evaluator = Evaluator(scenario_path)
        oracle_results = evaluator.run_oracles()

        # Display results
        print("\n=== Current State Oracle ===")
        current = oracle_results["current_state"]
        print(f"Files: {current.get('files', [])}")
        print(f"Production members: {current.get('members_in_production', [])}")
        print(f"Test members: {current.get('members_in_tests', [])}")
        print(f"Both: {current.get('members_in_both', [])}")

        print("\n=== History Oracle ===")
        history = oracle_results["history"]
        print(f"Inferred intent: {history.get('inferred_intent')}")
        print(f"Confidence: {history.get('confidence'):.2f}")
        print(f"Evidence:")
        for key, value in history.get('evidence', {}).items():
            print(f"  {key}: {value}")

        # Store for JSON output
        results[scenario_name] = {
            "current_state": current,
            "history": history,
            "semantic_assessment": {
                "status": "PENDING",
                "factual_correctness": "PENDING",
                "semantic_correctness": "PENDING",
                "notes": "Ghost comparison not yet integrated"
            }
        }

    # Save results
    output_file = Path(__file__).parent / "evaluation_results.json"
    with output_file.open("w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n{'=' * 70}")
    print(f"Evaluation complete")
    print(f"Results saved to: {output_file}")
    print(f"{'=' * 70}")

    return results

if __name__ == "__main__":
    evaluate_scenarios()
