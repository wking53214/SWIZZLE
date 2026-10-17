"""Old names for ``swizzle.integration.frequency_predictor``.

The predictor counts how often similar past decisions succeeded; it is not machine
learning, and the "ML" names said otherwise. They are kept as aliases so existing
imports still work, and importing this module raises a ``DeprecationWarning``. Use the names in
``frequency_predictor`` in new code.
"""

import warnings

from .frequency_predictor import (
    FrequencyModel as MLModel,
    FrequencyPredictor as MLPredictor,
    PredictionCache,
    create_frequency_predictor as create_ml_predictor,
)

warnings.warn(
    "swizzle.integration.ml_predictor is deprecated: the predictor counts how often similar past decisions "
    "succeeded and is not machine learning. Import FrequencyPredictor, FrequencyModel and "
    "create_frequency_predictor from swizzle.integration.frequency_predictor instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["MLModel", "MLPredictor", "PredictionCache", "create_ml_predictor"]
