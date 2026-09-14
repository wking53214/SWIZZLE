"""Tests for contrastive pair evaluation."""

import pytest
from pathlib import Path
from .contrastive_evaluation import ContrastiveEvaluator, ContrastiveResult
from .epistemic_model import SemanticTruth, IntentKind


def test_contrastive_result_dataclass():
    """Test ContrastiveResult construction."""
    result = ContrastiveResult(
        pair_id="test_pair_001",
        world_a_intent=IntentKind.INTENTIONAL_REFACTOR,
        world_b_intent=IntentKind.ACCIDENTAL_REMOVAL,
        shared_evidence_summary="Identical repository state"
    )

    assert result.pair_id == "test_pair_001"
    assert result.world_a_intent == IntentKind.INTENTIONAL_REFACTOR
    assert result.discriminated is False
    assert result.test_passed is False


def test_compare_oracle_assessments_discriminates():
    """Test discrimination when oracle assessments differ."""
    oracle_a = {
        "history": {
            "inferred_intent": "INTENTIONAL_REFACTOR",
            "confidence": 0.7
        }
    }

    oracle_b = {
        "history": {
            "inferred_intent": "ACCIDENTAL_REMOVAL",
            "confidence": 0.6
        }
    }

    truth_a = SemanticTruth(primary_intent=IntentKind.INTENTIONAL_REFACTOR)
    truth_b = SemanticTruth(primary_intent=IntentKind.ACCIDENTAL_REMOVAL)

    discriminated, confidence = ContrastiveEvaluator._compare_oracle_assessments(
        oracle_a, oracle_b, truth_a, truth_b
    )

    assert discriminated is True
    assert confidence > 0.5


def test_compare_oracle_assessments_no_discrimination():
    """Test lack of discrimination when oracle assessments match."""
    oracle_a = {
        "history": {
            "inferred_intent": "INTENTIONAL_REFACTOR",
            "confidence": 0.4
        }
    }

    oracle_b = {
        "history": {
            "inferred_intent": "INTENTIONAL_REFACTOR",
            "confidence": 0.4
        }
    }

    truth_a = SemanticTruth(primary_intent=IntentKind.INTENTIONAL_REFACTOR)
    truth_b = SemanticTruth(primary_intent=IntentKind.ACCIDENTAL_REMOVAL)

    discriminated, confidence = ContrastiveEvaluator._compare_oracle_assessments(
        oracle_a, oracle_b, truth_a, truth_b
    )

    assert discriminated is False
    assert confidence < 0.5


def test_measure_discrimination_quality():
    """Test discrimination quality metrics calculation."""
    results = [
        ContrastiveResult(
            pair_id="pair_001",
            world_a_intent=IntentKind.INTENTIONAL_REFACTOR,
            world_b_intent=IntentKind.ACCIDENTAL_REMOVAL,
            shared_evidence_summary="test",
            discriminated=True,
            discrimination_confidence=0.8
        ),
        ContrastiveResult(
            pair_id="pair_002",
            world_a_intent=IntentKind.INTENTIONAL_REFACTOR,
            world_b_intent=IntentKind.SECURITY_FIX,
            shared_evidence_summary="test",
            discriminated=True,
            discrimination_confidence=0.7
        ),
        ContrastiveResult(
            pair_id="pair_003",
            world_a_intent=IntentKind.ACCIDENTAL_REMOVAL,
            world_b_intent=IntentKind.SECURITY_FIX,
            shared_evidence_summary="test",
            discriminated=False,
            discrimination_confidence=0.4
        ),
    ]

    metrics = ContrastiveEvaluator.measure_discrimination_quality(results)

    assert metrics["total_pairs"] == 3
    assert metrics["discriminated"] == 2
    assert metrics["discrimination_rate"] == pytest.approx(2/3)
    assert metrics["average_confidence"] == pytest.approx(0.633, abs=0.01)


def test_measure_discrimination_quality_empty():
    """Test discrimination quality with empty results."""
    metrics = ContrastiveEvaluator.measure_discrimination_quality([])

    assert "error" in metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
