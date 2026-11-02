from datetime import datetime, timedelta, timezone
import math

import pytest

from data.market_data import MarketBar, MarketData
from regime import (
    GaussianHMMRegime,
    HMMRegimeError,
    HMMRegimeResult,
    HMMStateStatistics,
    RegimeAssessment,
    compare_regimes,
)


START = datetime(2024, 1, 1, tzinfo=timezone.utc)


def synthetic_market_data(count: int = 80) -> MarketData:
    close = 100.0
    bars = []
    for index in range(count):
        if index:
            drift = 0.002 if index < count // 2 else -0.001
            oscillation = 0.006 * math.sin(index * 1.7)
            close *= math.exp(drift + oscillation)
        daily_range = close * (0.004 if index < count // 2 else 0.025)
        bars.append(
            MarketBar(
                timestamp=START + timedelta(days=index),
                open=close,
                high=close + daily_range / 2,
                low=close - daily_range / 2,
                close=close,
                volume=1000,
            )
        )
    return MarketData("TEST", tuple(bars))


def test_hmm_reproducibility_and_state_statistics() -> None:
    data = synthetic_market_data()

    first = GaussianHMMRegime(random_state=7).fit_predict(data)
    second = GaussianHMMRegime(random_state=7).fit_predict(data)

    assert first == second
    assert first.timestamp == data.bars[-1].timestamp
    assert sum(item.observations for item in first.state_statistics.values()) == 79
    assert all(
        item.observations >= 0
        and (
            item.mean_log_return is None
            or math.isfinite(item.mean_log_return)
        )
        and (
            item.mean_normalized_range is None
            or math.isfinite(item.mean_normalized_range)
        )
        for item in first.state_statistics.values()
    )


def test_hmm_requires_seed_and_sufficient_history() -> None:
    with pytest.raises(TypeError):
        GaussianHMMRegime()
    with pytest.raises(HMMRegimeError, match="Insufficient history"):
        GaussianHMMRegime(random_state=1).fit_predict(synthetic_market_data(8))


def test_hmm_rejects_unordered_or_invalid_market_bars() -> None:
    bars = synthetic_market_data(12).bars
    with pytest.raises(HMMRegimeError, match="chronologically ordered"):
        GaussianHMMRegime(random_state=1).fit_predict(
            MarketData("TEST", (bars[0], bars[2], bars[1], *bars[3:]))
        )


def test_regime_comparison_compares_statistical_drift_not_state_number() -> None:
    deterministic = RegimeAssessment(
        ticker="TEST",
        timestamp=START,
        regime="BEAR",
        metrics={},
        evidence={},
        reason_codes=(),
    )
    stats = HMMStateStatistics(0, -0.01, 0.02, 0.03, 30)
    hmm = HMMRegimeResult(
        ticker="TEST",
        timestamp=START,
        state_statistics={0: stats, 1: HMMStateStatistics(1, 0.01, 0.01, 0.01, 20)},
        state_labels={
            0: "NEGATIVE_DRIFT_HIGH_VOLATILITY",
            1: "POSITIVE_DRIFT_LOW_VOLATILITY",
        },
        hidden_state_id=0,
        statistical_label="NEGATIVE_DRIFT_HIGH_VOLATILITY",
        statistics=stats,
        warnings=(),
    )

    comparison = compare_regimes(deterministic, hmm)

    assert comparison.hidden_state_id == 0
    assert comparison.agreement is True
    assert comparison.statistical_label.startswith("NEGATIVE_DRIFT")


def test_regime_comparison_reports_undefined_for_underrepresented_hmm_state() -> None:
    deterministic = RegimeAssessment(
        ticker="TEST",
        timestamp=START,
        regime="BEAR",
        metrics={},
        evidence={},
        reason_codes=(),
    )
    stats = HMMStateStatistics(1, None, None, None, 0)
    hmm = HMMRegimeResult(
        ticker="TEST",
        timestamp=START,
        state_statistics={1: stats},
        state_labels={1: "INSUFFICIENT_OBSERVATIONS"},
        hidden_state_id=1,
        statistical_label="INSUFFICIENT_OBSERVATIONS",
        statistics=stats,
        warnings=(),
    )

    assert compare_regimes(deterministic, hmm).agreement is None


def test_regime_comparison_rejects_mismatched_timestamps() -> None:
    deterministic = RegimeAssessment(
        ticker="TEST",
        timestamp=START,
        regime="BEAR",
        metrics={},
        evidence={},
        reason_codes=(),
    )
    stats = HMMStateStatistics(0, -0.01, 0.02, 0.03, 30)
    hmm = HMMRegimeResult(
        ticker="TEST",
        timestamp=START + timedelta(days=1),
        state_statistics={0: stats},
        state_labels={0: "NEGATIVE_DRIFT_HIGH_VOLATILITY"},
        hidden_state_id=0,
        statistical_label="NEGATIVE_DRIFT_HIGH_VOLATILITY",
        statistics=stats,
        warnings=(),
    )

    with pytest.raises(ValueError, match="same timestamp"):
        compare_regimes(deterministic, hmm)
