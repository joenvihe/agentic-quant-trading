from datetime import datetime, timezone
import math

import pytest

from features.engine import FeatureRow, FeatureSeries
from signals import MovingAverageCrossSignal, Signal, SignalDirection
from signals.trend import SignalGenerationError


NOW = datetime(2025, 1, 2, tzinfo=timezone.utc)


def feature_series(
    *, sma_20: float | None = 110.0, sma_50: float | None = 100.0
) -> FeatureSeries:
    return FeatureSeries(
        ticker="SPY",
        rows=(
            FeatureRow(
                timestamp=NOW,
                values={"sma_20": sma_20, "sma_50": sma_50},
            ),
        ),
    )


def test_moving_average_signal_is_long_when_fast_average_is_above_slow() -> None:
    signal = MovingAverageCrossSignal().generate(feature_series())

    assert signal.direction is SignalDirection.LONG
    assert signal.strength == 1.0
    assert signal.symbol == "SPY"
    assert signal.timestamp == NOW


@pytest.mark.parametrize(
    ("fast", "slow"),
    [(100.0, 100.0), (90.0, 100.0)],
)
def test_moving_average_signal_is_flat_when_fast_is_not_above_slow(
    fast: float, slow: float
) -> None:
    signal = MovingAverageCrossSignal().generate(
        feature_series(sma_20=fast, sma_50=slow)
    )

    assert signal.direction is SignalDirection.FLAT
    assert signal.strength == 0.0


def test_missing_moving_average_history_returns_flat_with_reason() -> None:
    signal = MovingAverageCrossSignal().generate(
        feature_series(sma_20=None, sma_50=None)
    )

    assert signal.direction is SignalDirection.FLAT
    assert signal.metadata["reason"] == "insufficient_history"


def test_empty_feature_history_raises_clear_error() -> None:
    with pytest.raises(SignalGenerationError, match="no features"):
        MovingAverageCrossSignal().generate(FeatureSeries("SPY", ()))


@pytest.mark.parametrize(
    ("fast_window", "slow_window"),
    [(50, 20), (20, 20), (0, 50), (10, 50), (20, 300)],
)
def test_rejects_invalid_or_unavailable_sma_windows(
    fast_window: int, slow_window: int
) -> None:
    with pytest.raises(ValueError, match="Windows"):
        MovingAverageCrossSignal(fast_window, slow_window)


@pytest.mark.parametrize("strength", [-0.01, 1.01, math.nan, math.inf])
def test_signal_strength_must_be_finite_and_between_zero_and_one(
    strength: float,
) -> None:
    with pytest.raises(ValueError, match="strength"):
        Signal(
            symbol="SPY",
            timestamp=NOW,
            direction=SignalDirection.FLAT,
            strength=strength,
            source="test",
        )


def test_signal_requires_non_empty_symbol_and_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="symbol"):
        Signal("", NOW, SignalDirection.FLAT, 0.0, "test")
    with pytest.raises(ValueError, match="timezone-aware"):
        Signal(
            "SPY",
            datetime(2025, 1, 2),
            SignalDirection.FLAT,
            0.0,
            "test",
        )


def test_signal_direction_must_use_the_defined_enum() -> None:
    with pytest.raises(ValueError, match="SignalDirection"):
        Signal(
            "SPY",
            NOW,
            "BUY",  # type: ignore[arg-type]
            1.0,
            "test",
        )
