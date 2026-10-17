"""Old names for ``swizzle.integration.frequency_predictor``.

The predictor counts how often similar past decisions succeeded; it is not machine
learning, and the "ML" names said otherwise. They are kept as aliases so existing
imports still work. Use the names in ``frequency_predictor`` in new code.
"""

from .frequency_predictor import (
    FrequencyModel as MLModel,
    FrequencyPredictor as MLPredictor,
    PredictionCache,
    create_frequency_predictor as create_ml_predictor,
)

__all__ = ["MLModel", "MLPredictor", "PredictionCache", "create_ml_predictor"]
