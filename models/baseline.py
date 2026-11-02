"""Deterministic logistic-regression baseline using a train-only scaler."""

import math
import random
from typing import Sequence

from models.datasets import DatasetSample
from models.preprocessing import FittedStandardizer, fit_standardizer
from models.types import MLSignal, ModelError


class BaselineClassifier:
    def __init__(
        self,
        random_state: int,
        max_iter: int = 500,
        learning_rate: float = 0.1,
        l2: float = 0.01,
    ) -> None:
        if (
            isinstance(random_state, bool)
            or not isinstance(random_state, int)
            or random_state < 0
        ):
            raise ValueError("random_state must be a non-negative integer.")
        if (
            isinstance(max_iter, bool)
            or not isinstance(max_iter, int)
            or max_iter <= 0
        ):
            raise ValueError("max_iter must be a positive integer.")
        if not math.isfinite(learning_rate) or learning_rate <= 0:
            raise ValueError("learning_rate must be positive and finite.")
        if not math.isfinite(l2) or l2 < 0:
            raise ValueError("l2 must be non-negative and finite.")
        self.random_state = random_state
        self.max_iter = max_iter
        self.learning_rate = learning_rate
        self.l2 = l2
        self._scaler: FittedStandardizer | None = None
        self._weights: tuple[float, ...] | None = None
        self._intercept = 0.0

    @staticmethod
    def _sigmoid(value: float) -> float:
        if value >= 0:
            return 1.0 / (1.0 + math.exp(-min(value, 709.0)))
        exponential = math.exp(max(value, -709.0))
        return exponential / (1.0 + exponential)

    def fit(self, samples: Sequence[DatasetSample]) -> "BaselineClassifier":
        if not samples:
            raise ModelError("Cannot fit the baseline without training samples.")
        feature_names = tuple(samples[0].features)
        if any(tuple(sample.features) != feature_names for sample in samples):
            raise ModelError("Training samples must have identical features.")
        self._scaler = fit_standardizer(samples, feature_names)
        matrix = [self._scaler.transform(sample.features) for sample in samples]
        labels = [sample.target for sample in samples]
        generator = random.Random(self.random_state)
        weights = [generator.uniform(-0.01, 0.01) for _ in feature_names]
        intercept = 0.0
        sample_count = len(samples)
        for _ in range(self.max_iter):
            errors = [
                self._sigmoid(
                    intercept
                    + sum(weight * value for weight, value in zip(weights, row))
                )
                - label
                for row, label in zip(matrix, labels)
            ]
            intercept -= self.learning_rate * math.fsum(errors) / sample_count
            for column in range(len(weights)):
                gradient = math.fsum(
                    error * row[column]
                    for error, row in zip(errors, matrix)
                ) / sample_count + self.l2 * weights[column]
                weights[column] -= self.learning_rate * gradient
        self._weights = tuple(weights)
        self._intercept = intercept
        return self

    def predict(self, samples: Sequence[DatasetSample]) -> tuple[MLSignal, ...]:
        if self._scaler is None or self._weights is None:
            raise ModelError("Baseline classifier must be fitted before prediction.")
        signals: list[MLSignal] = []
        for sample in samples:
            values = self._scaler.transform(sample.features)
            probability = self._sigmoid(
                self._intercept
                + math.fsum(
                    weight * value for weight, value in zip(self._weights, values)
                )
            )
            signals.append(
                MLSignal(
                    symbol=sample.symbol,
                    feature_timestamp=sample.feature_timestamp,
                    predicted_class=int(probability >= 0.5),
                    positive_probability=probability,
                    model_name="logistic_baseline",
                )
            )
        return tuple(signals)

    @property
    def scaler(self) -> FittedStandardizer:
        if self._scaler is None:
            raise ModelError("Baseline classifier has not been fitted.")
        return self._scaler
