"""XGBoost binary classifier with explicit seed and chronological callers."""

import math
from typing import Protocol, Sequence

from models.datasets import DatasetSample
from models.types import MLSignal, ModelError


class _XGBEstimator(Protocol):
    def fit(self, values: list[list[float]], labels: list[int]) -> object: ...

    def predict(self, values: list[list[float]]) -> list[int]: ...

    def predict_proba(self, values: list[list[float]]) -> list[list[float]]: ...


class XGBoostClassifier:
    def __init__(
        self,
        random_state: int,
        n_estimators: int = 100,
        max_depth: int = 3,
        learning_rate: float = 0.05,
    ) -> None:
        if (
            isinstance(random_state, bool)
            or not isinstance(random_state, int)
            or random_state < 0
        ):
            raise ValueError("random_state must be a non-negative integer.")
        if (
            isinstance(n_estimators, bool)
            or not isinstance(n_estimators, int)
            or n_estimators <= 0
        ):
            raise ValueError("n_estimators must be a positive integer.")
        if (
            isinstance(max_depth, bool)
            or not isinstance(max_depth, int)
            or max_depth <= 0
        ):
            raise ValueError("max_depth must be a positive integer.")
        if not math.isfinite(learning_rate) or not 0 < learning_rate <= 1:
            raise ValueError("learning_rate must be in (0, 1].")
        self.random_state = random_state
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self._estimator: _XGBEstimator | None = None
        self._feature_names: tuple[str, ...] | None = None

    def fit(self, samples: Sequence[DatasetSample]) -> "XGBoostClassifier":
        if not samples:
            raise ModelError("Cannot fit XGBoost without training samples.")
        labels = [sample.target for sample in samples]
        if len(set(labels)) < 2:
            raise ModelError("XGBoost training data must contain both classes.")
        names = tuple(samples[0].features)
        if any(tuple(sample.features) != names for sample in samples):
            raise ModelError("Training samples must have identical features.")
        try:
            from xgboost import XGBClassifier
        except ImportError as exc:
            raise ModelError(
                "XGBoost is required; install the 'xgboost' project dependency."
            ) from exc
        estimator = XGBClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            random_state=self.random_state,
            n_jobs=1,
            tree_method="hist",
            eval_metric="logloss",
            verbosity=0,
        )
        matrix = [[sample.features[name] for name in names] for sample in samples]
        try:
            estimator.fit(matrix, labels)
        except (ValueError, TypeError) as exc:
            raise ModelError(f"XGBoost training failed: {exc}") from exc
        self._estimator = estimator
        self._feature_names = names
        return self

    def predict(self, samples: Sequence[DatasetSample]) -> tuple[MLSignal, ...]:
        if self._estimator is None or self._feature_names is None:
            raise ModelError("XGBoost classifier must be fitted before prediction.")
        if any(tuple(sample.features) != self._feature_names for sample in samples):
            raise ModelError("Prediction features differ from the fitted feature set.")
        matrix = [
            [sample.features[name] for name in self._feature_names]
            for sample in samples
        ]
        predicted = self._estimator.predict(matrix)
        probabilities = self._estimator.predict_proba(matrix)
        return tuple(
            MLSignal(
                symbol=sample.symbol,
                feature_timestamp=sample.feature_timestamp,
                predicted_class=int(label),
                positive_probability=float(probability[1]),
                model_name="xgboost",
            )
            for sample, label, probability in zip(samples, predicted, probabilities)
        )
