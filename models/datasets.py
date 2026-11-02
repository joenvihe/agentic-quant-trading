"""Leakage-aware tabular dataset construction and chronological splitting."""

from dataclasses import dataclass
from datetime import datetime
import math
from types import MappingProxyType
from typing import Mapping, Sequence

from data.market_data import MarketData
from features.engine import FeatureSeries
from models.targets import generate_direction_targets


class DatasetError(ValueError):
    """Raised when feature and label data cannot be aligned safely."""


@dataclass(frozen=True)
class DatasetSample:
    symbol: str
    feature_timestamp: datetime
    target_timestamp: datetime
    features: Mapping[str, float]
    target: int

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise DatasetError("Sample symbol cannot be empty.")
        if (
            self.feature_timestamp.tzinfo is None
            or self.feature_timestamp.utcoffset() is None
            or self.target_timestamp.tzinfo is None
            or self.target_timestamp.utcoffset() is None
        ):
            raise DatasetError("Sample timestamps must be timezone-aware.")
        if self.target_timestamp <= self.feature_timestamp:
            raise DatasetError("Target timestamp must follow feature timestamp.")
        if isinstance(self.target, bool) or self.target not in (0, 1):
            raise DatasetError("Target must be 0 or 1.")
        if not self.features:
            raise DatasetError("Sample must contain at least one feature.")
        normalized: dict[str, float] = {}
        for name, value in self.features.items():
            if not name.strip() or isinstance(value, bool):
                raise DatasetError("Feature names and values must be valid.")
            numeric_value = float(value)
            if not math.isfinite(numeric_value):
                raise DatasetError(f"Feature {name!r} must be finite.")
            normalized[name] = numeric_value
        object.__setattr__(self, "features", MappingProxyType(normalized))


@dataclass(frozen=True)
class MLDataset:
    samples: tuple[DatasetSample, ...]
    feature_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.samples:
            raise DatasetError("Dataset cannot be empty.")
        if (
            not self.feature_names
            or any(not name.strip() for name in self.feature_names)
            or len(set(self.feature_names)) != len(self.feature_names)
        ):
            raise DatasetError("Feature names must be non-empty and unique.")
        previous: datetime | None = None
        for sample in self.samples:
            if tuple(sample.features) != self.feature_names:
                raise DatasetError("All samples must use the same ordered features.")
            if previous is not None and sample.feature_timestamp <= previous:
                raise DatasetError(
                    "Dataset samples must have unique, increasing feature timestamps."
                )
            previous = sample.feature_timestamp


@dataclass(frozen=True)
class DatasetSplit:
    train: tuple[DatasetSample, ...]
    test: tuple[DatasetSample, ...]
    train_end: datetime
    test_start: datetime

    def __post_init__(self) -> None:
        if not self.train or not self.test:
            raise DatasetError("Temporal split requires non-empty train and test.")
        if (
            self.train_end.tzinfo is None
            or self.train_end.utcoffset() is None
            or self.test_start.tzinfo is None
            or self.test_start.utcoffset() is None
        ):
            raise DatasetError("Split boundaries must be timezone-aware.")
        if self.train_end >= self.test_start:
            raise DatasetError("Training must end before testing starts.")
        if self.train_end != max(sample.feature_timestamp for sample in self.train):
            raise DatasetError("train_end must match the final training feature.")
        if self.test_start != min(sample.feature_timestamp for sample in self.test):
            raise DatasetError("test_start must match the first test feature.")
        if any(sample.target_timestamp >= self.test_start for sample in self.train):
            raise DatasetError("Training labels overlap the test period.")
        if any(sample.feature_timestamp < self.test_start for sample in self.test):
            raise DatasetError("Test samples precede the test period.")


def build_ml_dataset(
    market_data: MarketData,
    features: FeatureSeries,
    horizon: int,
    threshold: float,
    feature_names: Sequence[str] | None = None,
) -> MLDataset:
    """Join causal per-bar features with forward targets, dropping NaN rows."""
    if market_data.ticker.strip().upper() != features.ticker.strip().upper():
        raise DatasetError("Market data and features must refer to the same ticker.")
    if len(market_data.bars) != len(features.rows):
        raise DatasetError("Market data and feature rows must have equal length.")
    previous_timestamp: datetime | None = None
    for bar, row in zip(market_data.bars, features.rows):
        if (
            bar.timestamp.tzinfo is None
            or bar.timestamp.utcoffset() is None
            or (
                previous_timestamp is not None
                and bar.timestamp <= previous_timestamp
            )
        ):
            raise DatasetError("Market timestamps must be aware, unique and ordered.")
        if bar.timestamp != row.timestamp:
            raise DatasetError("Feature timestamps must align with market bars.")
        previous_timestamp = bar.timestamp
    if feature_names is None:
        names = tuple(features.rows[0].values) if features.rows else ()
    else:
        names = tuple(feature_names)
    if not names or len(set(names)) != len(names):
        raise DatasetError("Select one or more unique feature names.")
    missing = sorted(
        {
            name
            for row in features.rows
            for name in names
            if name not in row.values
        }
    )
    if missing:
        raise DatasetError(f"Selected features are missing: {', '.join(missing)}.")
    targets = generate_direction_targets(market_data, horizon, threshold)
    samples: list[DatasetSample] = []
    for row, label in zip(features.rows, targets):
        values = {name: row.values[name] for name in names}
        if any(value is None for value in values.values()):
            continue
        try:
            numeric = {name: float(value) for name, value in values.items()}
        except (TypeError, ValueError, OverflowError) as exc:
            raise DatasetError("Feature values must be numeric or missing.") from exc
        if any(not math.isfinite(value) for value in numeric.values()):
            continue
        samples.append(
            DatasetSample(
                symbol=market_data.ticker,
                feature_timestamp=label.feature_timestamp,
                target_timestamp=label.target_timestamp,
                features=numeric,
                target=label.target,
            )
        )
    if not samples:
        raise DatasetError("No complete feature rows are available for training.")
    return MLDataset(tuple(samples), names)


def temporal_train_test_split(
    dataset: MLDataset, test_fraction: float = 0.2
) -> DatasetSplit:
    """Split chronologically and purge train labels reaching the first test bar."""
    if not math.isfinite(test_fraction) or not 0.0 < test_fraction < 1.0:
        raise DatasetError("test_fraction must be between 0 and 1.")
    samples = dataset.samples
    if len(samples) < 3:
        raise DatasetError("At least three samples are required for a temporal split.")
    split_index = min(
        len(samples) - 1, max(1, int(len(samples) * (1 - test_fraction)))
    )
    test_start = samples[split_index].feature_timestamp
    train = tuple(
        sample
        for sample in samples[:split_index]
        if sample.target_timestamp < test_start
    )
    test = samples[split_index:]
    if not train:
        raise DatasetError(
            "Temporal split leaves no training samples after target-horizon purge."
        )
    return DatasetSplit(
        train=train,
        test=test,
        train_end=max(sample.feature_timestamp for sample in train),
        test_start=test_start,
    )
