"""Trend signal generators using existing moving-average features."""

import math

from features.engine import FEATURE_NAMES, FeatureSeries
from signals.types import Signal, SignalDirection


class SignalGenerationError(Exception):
    """Raised when features cannot be converted into a valid signal."""


class MovingAverageCrossSignal:
    """Long-only trend state based on two existing simple moving averages."""

    def __init__(self, fast_window: int = 20, slow_window: int = 50) -> None:
        available_windows = _available_sma_windows()
        if (
            isinstance(fast_window, bool)
            or isinstance(slow_window, bool)
            or not isinstance(fast_window, int)
            or not isinstance(slow_window, int)
            or fast_window not in available_windows
            or slow_window not in available_windows
            or fast_window >= slow_window
        ):
            raise ValueError(
                "Windows must be available SMA periods with fast_window "
                "smaller than slow_window."
            )
        self.fast_window = fast_window
        self.slow_window = slow_window

    def generate(self, features: FeatureSeries) -> Signal:
        if not features.rows:
            raise SignalGenerationError(
                f"{features.ticker}: no features are available."
            )

        latest = features.rows[-1]
        fast_name = f"sma_{self.fast_window}"
        slow_name = f"sma_{self.slow_window}"
        fast = latest.values.get(fast_name)
        slow = latest.values.get(slow_name)

        if fast is not None and not math.isfinite(fast):
            raise SignalGenerationError(f"{fast_name} must be finite.")
        if slow is not None and not math.isfinite(slow):
            raise SignalGenerationError(f"{slow_name} must be finite.")

        available = fast is not None and slow is not None
        is_long = fast is not None and slow is not None and fast > slow
        return Signal(
            symbol=features.ticker,
            timestamp=latest.timestamp,
            direction=SignalDirection.LONG if is_long else SignalDirection.FLAT,
            strength=1.0 if is_long else 0.0,
            source="moving_average_cross",
            metadata={
                "fast_window": self.fast_window,
                "slow_window": self.slow_window,
                "fast_average": fast,
                "slow_average": slow,
                "reason": (
                    "fast_average_above_slow_average"
                    if is_long
                    else "insufficient_history"
                    if not available
                    else "fast_average_not_above_slow_average"
                ),
            },
        )


def _available_sma_windows() -> frozenset[int]:
    return frozenset(
        int(name.removeprefix("sma_"))
        for name in FEATURE_NAMES
        if name.startswith("sma_")
    )
