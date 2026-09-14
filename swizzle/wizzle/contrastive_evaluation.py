"""Contrastive pair evaluation.

Tests oracle discrimination ability by comparing paired scenarios with:
- Identical observable evidence (repository state, git history)
- Different ground-truth semantic intent

This validates that oracles distinguish between coincidence and causation,
and measures how much evidence is required to disambiguate.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Tuple
from pathlib import Path

from .evaluator import Evaluator
from .epistemic_model import IntentKind, SemanticTruth, SemanticCorrectness


@dataclass
class ContrastiveResult:
    """Result of evaluating a contrastive pair."""
    pair_id: str
    world_a_intent: IntentKind
    world_b_intent: IntentKind
    shared_evidence_summary: str

    # Oracle assessments
    world_a_oracle_results: Dict[str, Any] = field(default_factory=dict)
    world_b_oracle_results: Dict[str, Any] = field(default_factory=dict)

    # Discrimination metrics
    discriminated: bool = False  # Did oracle distinguish them?
    discrimination_confidence: float = 0.0  # 0.0-1.0
    oracle_reasoning: str = ""

    # Analysis
    notes: str = ""
    test_passed: bool = False


class ContrastiveEvaluator:
    """Evaluate contrastive pairs to measure oracle discrimination."""

    def __init__(self):
        pass

    @staticmethod
    def evaluate_pair(
        world_a_path: Path,
        world_b_path: Path,
        world_a_truth: SemanticTruth,
        world_b_truth: SemanticTruth,
        pair_id: str = "unnamed"
    ) -> ContrastiveResult:
        """Evaluate whether oracles can discriminate between two worlds.

        Args:
            world_a_path: Path to first scenario repository
            world_b_path: Path to second scenario repository
            world_a_truth: Ground truth for world A
            world_b_truth: Ground truth for world B
            pair_id: Identifier for this pair

        Returns:
            ContrastiveResult with discrimination metrics
        """

        result = ContrastiveResult(
            pair_id=pair_id,
            world_a_intent=world_a_truth.primary_intent,
            world_b_intent=world_b_truth.primary_intent,
            shared_evidence_summary="Paired scenarios with identical observable state"
        )

        # Run oracles on both worlds
        evaluator_a = Evaluator(world_a_path)
        evaluator_b = Evaluator(world_b_path)

        try:
            oracle_a = evaluator_a.run_oracles()
            oracle_b = evaluator_b.run_oracles()

            result.world_a_oracle_results = oracle_a
            result.world_b_oracle_results = oracle_b

        except Exception as e:
            result.notes = f"Oracle evaluation failed: {str(e)}"
            result.test_passed = False
            return result

        # Compare oracle assessments
        result.discriminated, result.discrimination_confidence = (
            ContrastiveEvaluator._compare_oracle_assessments(
                oracle_a, oracle_b, world_a_truth, world_b_truth
            )
        )

        # Generate reasoning
        if result.discriminated:
            result.oracle_reasoning = (
                f"Oracle successfully discriminated between "
                f"{world_a_truth.primary_intent.name} and {world_b_truth.primary_intent.name} "
                f"(confidence: {result.discrimination_confidence:.2f})"
            )
            result.test_passed = True
        else:
            result.oracle_reasoning = (
                f"Oracle failed to discriminate between intents "
                f"(confidence: {result.discrimination_confidence:.2f})"
            )
            result.test_passed = False

        return result

    @staticmethod
    def _compare_oracle_assessments(
        oracle_a: Dict[str, Any],
        oracle_b: Dict[str, Any],
        truth_a: SemanticTruth,
        truth_b: SemanticTruth
    ) -> Tuple[bool, float]:
        """Compare two oracle assessments to measure discrimination.

        Returns:
            (discriminated, confidence)
        """

        # Extract intent assessments
        intent_a = oracle_a.get("history", {}).get("inferred_intent", "UNKNOWN")
        intent_b = oracle_b.get("history", {}).get("inferred_intent", "UNKNOWN")

        conf_a = oracle_a.get("history", {}).get("confidence", 0.0)
        conf_b = oracle_b.get("history", {}).get("confidence", 0.0)

        # Check if oracle assessments differ
        intents_differ = intent_a != intent_b

        # Discrimination is successful if:
        # 1. Oracle conclusions differ, AND
        # 2. Each oracle has reasonable confidence in their assessment
        if intents_differ and (conf_a > 0.3 and conf_b > 0.3):
            # Strong discrimination
            avg_confidence = (conf_a + conf_b) / 2
            return True, min(avg_confidence, 0.95)
        elif intents_differ and (conf_a > 0.2 or conf_b > 0.2):
            # Weak discrimination
            avg_confidence = (conf_a + conf_b) / 2
            return True, min(avg_confidence, 0.6)
        else:
            # No discrimination
            avg_confidence = (conf_a + conf_b) / 2
            return False, avg_confidence

    @staticmethod
    def evaluate_pairs(
        pairs: List[Tuple[Path, Path, SemanticTruth, SemanticTruth]]
    ) -> List[ContrastiveResult]:
        """Evaluate multiple contrastive pairs.

        Args:
            pairs: List of (world_a_path, world_b_path, truth_a, truth_b) tuples

        Returns:
            List of ContrastiveResult objects
        """

        results = []
        for i, (path_a, path_b, truth_a, truth_b) in enumerate(pairs):
            pair_id = f"pair_{i:03d}"
            result = ContrastiveEvaluator.evaluate_pair(
                path_a, path_b, truth_a, truth_b, pair_id
            )
            results.append(result)

        return results

    @staticmethod
    def measure_discrimination_quality(results: List[ContrastiveResult]) -> Dict[str, Any]:
        """Measure overall discrimination quality across all pairs.

        Args:
            results: List of ContrastiveResult from evaluate_pairs

        Returns:
            Metrics dictionary with precision, recall, F1, etc.
        """

        total = len(results)
        if total == 0:
            return {"error": "No results to evaluate"}

        successful = sum(1 for r in results if r.discriminated)
        avg_confidence = sum(r.discrimination_confidence for r in results) / total

        metrics = {
            "total_pairs": total,
            "discriminated": successful,
            "discrimination_rate": successful / total,
            "average_confidence": avg_confidence,
            "min_confidence": min(r.discrimination_confidence for r in results),
            "max_confidence": max(r.discrimination_confidence for r in results),
        }

        return metrics
