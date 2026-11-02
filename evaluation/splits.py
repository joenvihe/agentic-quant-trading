"""Chronological expanding and rolling train/test windows."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from data.market_data import MarketData


SplitMode = Literal["expanding", "rolling"]


@dataclass(frozen=True)
class TimeWindow:
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime

    def __post_init__(self) -> None:
        timestamps = (
            self.train_start,
            self.train_end,
            self.test_start,
            self.test_end,
        )
        if any(value.tzinfo is None or value.utcoffset() is None for value in timestamps):
            raise ValueError("TimeWindow timestamps must be timezone-aware.")
        if not (
            self.train_start <= self.train_end < self.test_start <= self.test_end
        ):
            raise ValueError(
                "TimeWindow requires train_start <= train_end < "
                "test_start <= test_end."
            )


class TemporalSplitError(ValueError):
    """Raised when chronological split settings or history are invalid."""


def generate_time_splits(
    market_data: MarketData,
    train_size: int,
    test_size: int,
    step_size: int | None = None,
    mode: SplitMode = "expanding",
) -> tuple[TimeWindow, ...]:
    """Build temporal folds using bar counts; never shuffle observations."""
    for name, value in (("train_size", train_size), ("test_size", test_size)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise TemporalSplitError(f"{name} must be a positive integer.")
    if step_size is None:
        step_size = test_size
    if isinstance(step_size, bool) or not isinstance(step_size, int) or step_size <= 0:
        raise TemporalSplitError("step_size must be a positive integer.")
    if mode not in ("expanding", "rolling"):
        raise TemporalSplitError(f"Unknown split mode: {mode}.")
    if not market_data.bars:
        raise TemporalSplitError("Insufficient history: market data is empty.")

    bars = market_data.bars
    seen: set[datetime] = set()
    previous: datetime | None = None
    for bar in bars:
        timestamp = bar.timestamp
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise TemporalSplitError("Market timestamps must be timezone-aware.")
        if timestamp in seen:
            raise TemporalSplitError("Market timestamps must be unique.")
        if previous is not None and timestamp <= previous:
            raise TemporalSplitError("Market timestamps must be ordered.")
        seen.add(timestamp)
        previous = timestamp

    windows: list[TimeWindow] = []
    train_end_index = train_size - 1
    while train_end_index + test_size < len(bars):
        train_start_index = (
            0 if mode == "expanding" else train_end_index - train_size + 1
        )
        test_start_index = train_end_index + 1
        test_end_index = test_start_index + test_size - 1
        windows.append(
            TimeWindow(
                train_start=bars[train_start_index].timestamp,
                train_end=bars[train_end_index].timestamp,
                test_start=bars[test_start_index].timestamp,
                test_end=bars[test_end_index].timestamp,
            )
        )
        train_end_index += step_size

    if not windows:
        raise TemporalSplitError(
            f"Insufficient history: need at least {train_size + test_size} bars."
        )
    return tuple(windows)


def slice_market_data(
    market_data: MarketData,
    start: datetime,
    end: datetime,
) -> MarketData:
    """Return bars in an inclusive time range while preserving source order."""
    if start.tzinfo is None or start.utcoffset() is None:
        raise TemporalSplitError("Split boundaries must be timezone-aware.")
    if end.tzinfo is None or end.utcoffset() is None or start > end:
        raise TemporalSplitError("Split range is invalid.")
    bars = tuple(
        bar for bar in market_data.bars if start <= bar.timestamp <= end
    )
    if not bars:
        raise TemporalSplitError("Insufficient history: split contains no bars.")
    return MarketData(ticker=market_data.ticker, bars=bars)
