"""Train-only numeric feature scaling."""

from dataclasses import dataclass
import math
from statistics import fmean, pstdev
from typing import Mapping, Sequence

from models.datasets import DatasetSample
from models.types import ModelError


@dataclass(frozen=True)
class FittedStandardizer:
    feature_names: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]

    def transform(self, features: Mapping[str, float]) -> tuple[float, ...]:
        if tuple(features) != self.feature_names:
            raise ModelError("Feature names and order do not match the fitted scaler.")
        transformed = tuple(
            (float(features[name]) - mean) / scale
            for name, mean, scale in zip(self.feature_names, self.means, self.scales)
        )
        if any(not math.isfinite(value) for value in transformed):
            raise ModelError("Scaler input values must be finite.")
        return transformed


def fit_standardizer(
    samples: Sequence[DatasetSample], feature_names: tuple[str, ...]
) -> FittedStandardizer:
    """Fit means/scales on the supplied training samples only."""
    if not samples:
        raise ModelError("Cannot fit a scaler without training samples.")
    if not feature_names or len(set(feature_names)) != len(feature_names):
        raise ModelError("Scaler feature names must be non-empty and unique.")
    columns = [
        [sample.features[name] for sample in samples]
        for name in feature_names
    ]
    means = tuple(fmean(values) for values in columns)
    scales = tuple(pstdev(values) or 1.0 for values in columns)
    return FittedStandardizer(feature_names, means, scales)
