#!/usr/bin/env python3
"""Test Ghost Simulator: Run full evaluation pipeline on WIZZLE corpus.

This script simulates Ghost findings on all scenarios and reports:
- What Ghost gets right/wrong
- Where WIZZLE catches overclaims
- Oracle discrimination ability
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any

from .ghost_simulator import GhostSimulator
from .evaluator import Evaluator
from .epistemic_model import IntentKind, SemanticCorrectness


def run_scenario_evaluation(scenario_path: Path, intent: IntentKind) -> Dict[str, Any]:
    """Evaluate one scenario against simulated Ghost."""
    print(f"\n{'='*60}")
    print(f"Evaluating: {scenario_path.name}")
    print(f"Ground truth intent: {intent.name}")
    print(f"{'='*60}")

    # Run oracles
    evaluator = Evaluator(scenario_path)
    oracle_results = evaluator.run_oracles()

    print(f"\nOracle Assessment:")
    print(f"  Inferred intent: {oracle_results.get('history', {}).get('inferred_intent')}")
    print(f"  Confidence: {oracle_results.get('history', {}).get('confidence', 0):.2%}")

    # Simulate Ghost and evaluate
    report = GhostSimulator.evaluate_scenario(
        scenario_path, oracle_results, intent
    )

    print(f"\nGhost Finding:")
    print(f"  Category: {report['ghost_finding']['category']}")
    print(f"  Severity: {report['ghost_finding']['severity']}")
    print(f"  Confidence: {report['ghost_finding']['confidence']:.1%}")

    print(f"\nWIZZLE Verdict:")
    print(f"  Semantic correctness: {report['verdict']['semantic_correctness']}")
    print(f"  Factual correctness: {report['verdict']['factual_correctness']}")

    if report['verdict']['overclaimed']:
        print(f"  ⚠️  OVERCLAIMED - Ghost exceeded evidence entitlement")
    elif report['verdict']['underclaimed']:
        print(f"  ⚠️  UNDERCLAIMED - Ghost was too conservative")
    else:
        print(f"  ✓ JUSTIFIED - Ghost's conclusion is appropriate")

    return report


def main():
    """Run full corpus evaluation."""
    corpus_dir = Path(__file__).parent / "corpus"

    print("\n" + "="*60)
    print("WIZZLE Ghost Simulator Test Run")
    print("Bouncing Ghost findings off WIZZLE evaluation pipeline")
    print("="*60)

    # Map scenarios to ground truth intents
    scenario_intents = {
        "phantom_intentional_refactor": IntentKind.INTENTIONAL_REFACTOR,
        "phantom_accidental_removal": IntentKind.ACCIDENTAL_REMOVAL,
        "medium_priority_intentional_removal": IntentKind.INTENTIONAL_REFACTOR,
        "security_fix_removal": IntentKind.SECURITY_FIX,
        "dead_code_cleanup": IntentKind.DEAD_CODE_CLEANUP,
        "api_deprecation": IntentKind.INTENTIONAL_REFACTOR,
        "revert_removal": IntentKind.REVERT,
        "branch_divergence": IntentKind.INTENTIONAL_REFACTOR,
        "test_only_migration": IntentKind.TEST_ONLY_MIGRATION,
        "partial_replacement": IntentKind.INTENTIONAL_REFACTOR,
        "cherry_pick_removal": IntentKind.INTENTIONAL_REFACTOR,
        "multiple_removal": IntentKind.INTENTIONAL_REFACTOR,
    }

    results = []
    overclaims_caught = 0
    total_scenarios = 0

    for scenario_name, intent in scenario_intents.items():
        scenario_path = corpus_dir / scenario_name
        if not scenario_path.exists():
            print(f"\n⚠️  Scenario not found: {scenario_path}")
            continue

        total_scenarios += 1
        try:
            report = run_scenario_evaluation(scenario_path, intent)
            results.append(report)

            if report['would_catch_overclaim']:
                overclaims_caught += 1
                print(f"  🎯 CAUGHT OVERCLAIM!")

        except Exception as e:
            print(f"  ❌ Error evaluating scenario: {e}")
            results.append({
                "scenario": scenario_name,
                "error": str(e)
            })

    # Summary report
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"\nScenarios evaluated: {total_scenarios}")
    print(f"Overclaims caught by WIZZLE: {overclaims_caught}")

    # Verdict breakdown
    verdicts = {}
    for report in results:
        if "verdict" in report:
            verdict = report["verdict"]["semantic_correctness"]
            verdicts[verdict] = verdicts.get(verdict, 0) + 1

    print(f"\nVerdict Breakdown:")
    for verdict, count in sorted(verdicts.items()):
        print(f"  {verdict}: {count}")

    # Detailed results file
    results_file = Path(__file__).parent / "ghost_simulation_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nDetailed results saved to: {results_file}")

    return 0 if overclaims_caught > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
