"""Model and prediction contracts, distinct from orders and positions."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping


class ModelError(ValueError):
    """Raised when a supervised model cannot be trained or evaluated."""


@dataclass(frozen=True)
class MLSignal:
    symbol: str
    feature_timestamp: datetime
    predicted_class: int
    positive_probability: float
    model_name: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty.")
        if (
            self.feature_timestamp.tzinfo is None
            or self.feature_timestamp.utcoffset() is None
        ):
            raise ValueError("feature_timestamp must be timezone-aware.")
        if (
            isinstance(self.predicted_class, bool)
            or self.predicted_class not in (0, 1)
        ):
            raise ValueError("predicted_class must be 0 or 1.")
        if not 0.0 <= self.positive_probability <= 1.0:
            raise ValueError("positive_probability must be between 0 and 1.")
        if not self.model_name.strip():
            raise ValueError("model_name cannot be empty.")
