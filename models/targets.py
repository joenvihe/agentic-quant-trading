"""Forward-return binary labels with explicit feature/target timestamps."""

from dataclasses import dataclass
from datetime import datetime
import math

from data.market_data import MarketData


@dataclass(frozen=True)
class DirectionTarget:
    feature_timestamp: datetime
    target_timestamp: datetime
    target: int

    def __post_init__(self) -> None:
        if (
            self.feature_timestamp.tzinfo is None
            or self.feature_timestamp.utcoffset() is None
            or self.target_timestamp.tzinfo is None
            or self.target_timestamp.utcoffset() is None
        ):
            raise ValueError("Target timestamps must be timezone-aware.")
        if self.target_timestamp <= self.feature_timestamp:
            raise ValueError("target_timestamp must follow feature_timestamp.")
        if isinstance(self.target, bool) or self.target not in (0, 1):
            raise ValueError("target must be 0 or 1.")


def generate_direction_targets(
    market_data: MarketData, horizon: int, threshold: float
) -> tuple[DirectionTarget, ...]:
    """Label each usable bar; trailing bars without future closes are omitted."""
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon <= 0:
        raise ValueError("horizon must be a positive integer.")
    if isinstance(threshold, bool) or not math.isfinite(threshold):
        raise ValueError("threshold must be finite.")
    bars = market_data.bars
    if len(bars) <= horizon:
        return ()
    previous_timestamp: datetime | None = None
    for bar in bars:
        if (
            bar.timestamp.tzinfo is None
            or bar.timestamp.utcoffset() is None
            or (
                previous_timestamp is not None
                and bar.timestamp <= previous_timestamp
            )
        ):
            raise ValueError("Market timestamps must be aware, unique and ordered.")
        previous_timestamp = bar.timestamp
        if not math.isfinite(bar.close) or bar.close <= 0:
            raise ValueError("Close prices must be positive and finite.")
    result: list[DirectionTarget] = []
    for index in range(len(bars) - horizon):
        current = bars[index]
        future = bars[index + horizon]
        if (
            not math.isfinite(current.close)
            or not math.isfinite(future.close)
            or current.close <= 0
            or future.close <= 0
        ):
            raise ValueError("Close prices must be positive and finite.")
        if future.timestamp <= current.timestamp:
            raise ValueError("Target timestamps must follow feature timestamps.")
        forward_return = future.close / current.close - 1.0
        result.append(
            DirectionTarget(
                feature_timestamp=current.timestamp,
                target_timestamp=future.timestamp,
                target=int(forward_return > threshold),
            )
        )
    return tuple(result)
