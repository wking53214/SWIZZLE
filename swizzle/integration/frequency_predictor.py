"""Frequency-based confidence prediction for autonomous decisions.

This is plain counting, not machine learning. For each (decision type, risk
level) pair it counts how often past decisions were approved and executed, and
blends that success rate with a base confidence:

    predicted = success_rate * action_similarity + (1 - action_similarity) * 0.5

A pair seen fewer than three times gets the neutral 0.5. Nothing is fitted,
nothing is trained by an optimiser, and there is no held-out evaluation, so the
output should be read as "what happened the last few times", not as a calibrated
probability. This module used to be called ``ml_predictor`` (``FrequencyPredictor``,
``FrequencyModel``); those names remain importable from ``swizzle.integration.ml_predictor``
as aliases, but they were misleading and new code should use the names here.
"""

from typing import Dict, Tuple
from dataclasses import dataclass
import statistics

from .unified_index import UnifiedIndex


@dataclass
class FrequencyModel:
    """Historical counts for one (decision type, risk level) pair. Not a fitted model."""
    decision_type: str
    risk_level: str
    approval_rate: float  # Historical approval rate
    execution_rate: float  # Historical execution rate
    avg_confidence: float  # Historical avg confidence
    success_rate: float  # Approved AND executed
    sample_count: int


class FrequencyPredictor:
    """Predicts decision confidence from how often similar past decisions succeeded."""

    def __init__(self, index: UnifiedIndex):
        self.index = index
        self.models: Dict[Tuple[str, str], FrequencyModel] = {}
        self._train_models()

    def _train_models(self) -> None:
        """Count outcomes per (decision type, risk level) from historical decisions."""
        for decision in self.index.decisions.values():
            key = (decision.type, decision.risk_level)

            if key not in self.models:
                self.models[key] = self._create_model_for_key(key)

    def _create_model_for_key(self, key: Tuple[str, str]) -> FrequencyModel:
        """Create model for decision type + risk level."""
        dtype, risk = key
        decisions = [d for d in self.index.decisions.values()
                    if d.type == dtype and d.risk_level == risk]

        if not decisions:
            return FrequencyModel(
                decision_type=dtype,
                risk_level=risk,
                approval_rate=0.0,
                execution_rate=0.0,
                avg_confidence=0.5,
                success_rate=0.0,
                sample_count=0,
            )

        approved = sum(1 for d in decisions if d.approved)
        executed = sum(1 for d in decisions if d.executed)
        successful = sum(1 for d in decisions if d.approved and d.executed)
        confidences = [d.confidence for d in decisions]

        return FrequencyModel(
            decision_type=dtype,
            risk_level=risk,
            approval_rate=approved / len(decisions),
            execution_rate=executed / len(decisions),
            avg_confidence=statistics.mean(confidences) if confidences else 0.5,
            success_rate=successful / len(decisions),
            sample_count=len(decisions),
        )

    def predict_confidence(self, decision_type: str, risk_level: str,
                          action_similarity: float = 0.7) -> float:
        """Predict confidence for a decision based on historical patterns.

        Args:
            decision_type: Type of decision
            risk_level: Risk level (low/medium/high/critical)
            action_similarity: How similar action is to historical (0-1)

        Returns:
            Predicted confidence score (0-1)
        """
        key = (decision_type, risk_level)

        if key not in self.models:
            return 0.5  # Default confidence

        model = self.models[key]

        # Minimum samples for confidence
        if model.sample_count < 3:
            return 0.5

        # Base confidence from historical success rate
        base_confidence = model.success_rate

        # Adjust for pattern similarity
        adjusted = base_confidence * action_similarity + (1 - action_similarity) * 0.5

        # Clamp to valid range
        return min(1.0, max(0.0, adjusted))

    def get_model_stats(self) -> Dict[str, Dict]:
        """Get statistics for all trained models."""
        stats = {}
        for (dtype, risk), model in self.models.items():
            key = f"{dtype}_{risk}"
            stats[key] = {
                "decision_type": dtype,
                "risk_level": risk,
                "approval_rate": model.approval_rate,
                "execution_rate": model.execution_rate,
                "success_rate": model.success_rate,
                "avg_confidence": model.avg_confidence,
                "samples": model.sample_count,
            }
        return stats

    def suggest_confidence_adjustment(self, decision_type: str, risk_level: str,
                                     current_confidence: float) -> float:
        """Suggest adjusted confidence based on historical patterns.

        Returns adjusted confidence that better matches success likelihood.
        """
        key = (decision_type, risk_level)
        if key not in self.models:
            return current_confidence

        model = self.models[key]
        if model.sample_count < 3:
            return current_confidence

        # If historical success rate is higher than current confidence,
        # suggest increasing confidence
        if model.success_rate > current_confidence:
            adjustment = min(1.0, current_confidence + (model.success_rate - current_confidence) * 0.5)
        else:
            adjustment = current_confidence

        return adjustment


class PredictionCache:
    """Cache for predictions to avoid recomputation."""

    def __init__(self, predictor: FrequencyPredictor):
        self.predictor = predictor
        self.cache: Dict[str, float] = {}

    def get_prediction(self, decision_type: str, risk_level: str,
                       action_similarity: float = 0.7) -> float:
        """Get cached or compute prediction."""
        key = f"{decision_type}_{risk_level}_{action_similarity:.2f}"

        if key not in self.cache:
            self.cache[key] = self.predictor.predict_confidence(
                decision_type, risk_level, action_similarity
            )

        return self.cache[key]

    def clear_cache(self) -> None:
        """Clear prediction cache (call after the counts are rebuilt)."""
        self.cache.clear()


def create_frequency_predictor(index: UnifiedIndex) -> FrequencyPredictor:
    """Factory for the frequency predictor."""
    return FrequencyPredictor(index)
