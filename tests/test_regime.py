from datetime import datetime, timezone
import json
import math

import pytest

from config.regime import RegimeThresholds
from features.engine import FeatureRow, FeatureSeries
from regime.engine import RegimeError, detect_regime


def make_features(**overrides: float | None) -> FeatureSeries:
    values: dict[str, float | None] = {
        "sma_20": 112.0,
        "sma_50": 110.0,
        "sma_200": 100.0,
        "return_1m": 0.02,
        "return_3m": 0.05,
        "return_6m": 0.15,
        "return_12m": 0.20,
        "realized_volatility_20": 0.20,
        "atr_14": 1.0,
        "bollinger_band_width_20": 0.08,
        "distance_from_52w_high": -0.02,
    }
    values.update(overrides)
    return FeatureSeries(
        ticker="SPY",
        rows=(
            FeatureRow(
                timestamp=datetime(2025, 1, 2, tzinfo=timezone.utc),
                values=values,
            ),
        ),
    )


def test_classifies_strong_bull_and_returns_structured_evidence() -> None:
    result = detect_regime(make_features(), RegimeThresholds())
    output = result.to_dict()

    assert result.regime == "BULL_STRONG"
    assert result.metrics["atr_14_to_sma_20"] == pytest.approx(1 / 112)
    assert result.evidence["direction"]["state"] == "BULLISH"
    assert result.evidence["strength"]["state"] == "STRONG_BULLISH"
    assert result.evidence["volatility"]["state"] == "NORMAL"
    assert result.evidence["confirmation"]["state"] == "CONFIRMED_BULLISH"
    assert "BULLISH_DIRECTION_CONFIRMED_STRONG_AND_NORMAL_VOLATILITY" in (
        result.reason_codes
    )
    assert set(output) == {
        "ticker",
        "timestamp",
        "regime",
        "metrics",
        "evidence",
        "reason_codes",
    }
    json.dumps(output, allow_nan=False)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"realized_volatility_20": 0.45}, "CHAOTIC"),
        ({"atr_14": 112 * 0.03}, "CHAOTIC"),
        ({"realized_volatility_20": 0.30}, "BULL_VOLATILE"),
        ({"atr_14": 112 * 0.02}, "BULL_VOLATILE"),
        ({"return_6m": 0.10}, "BULL_STRONG"),
    ],
)
def test_threshold_boundaries_use_inclusive_comparisons(
    overrides: dict[str, float], expected: str
) -> None:
    result = detect_regime(make_features(**overrides), RegimeThresholds())

    assert result.regime == expected


def test_values_just_below_volatility_threshold_do_not_cross_it() -> None:
    result = detect_regime(
        make_features(realized_volatility_20=math.nextafter(0.30, 0.0)),
        RegimeThresholds(),
    )

    assert result.regime == "BULL_STRONG"
    assert result.evidence["volatility"]["state"] == "NORMAL"


def test_confirmation_threshold_requires_two_of_three_criteria() -> None:
    bearish_confirmed = detect_regime(
        make_features(sma_20=100, sma_50=110, return_1m=0.02),
        RegimeThresholds(),
    )
    exactly_two = detect_regime(
        make_features(sma_20=109.5, sma_50=110, return_1m=0.02),
        RegimeThresholds(),
    )

    assert bearish_confirmed.evidence["confirmation"]["bullish_agreements"] == 1
    assert bearish_confirmed.evidence["confirmation"]["bearish_agreements"] == 2
    assert bearish_confirmed.evidence["confirmation"]["bearish_criteria"] == {
        "return_1m_and_3m_negative": False,
        "sma_20_below_sma_50": True,
        "inferred_price_below_sma_50": True,
    }
    assert bearish_confirmed.evidence["confirmation"]["bullish_criteria"] == {
        "return_1m_and_3m_positive": True,
        "sma_20_above_sma_50": False,
        "inferred_price_above_sma_50": False,
    }
    assert bearish_confirmed.evidence["confirmation"]["state"] == "CONFIRMED_BEARISH"
    assert exactly_two.evidence["confirmation"]["bullish_agreements"] == 2
    assert exactly_two.evidence["confirmation"]["bearish_agreements"] == 1
    assert exactly_two.evidence["confirmation"]["bullish_criteria"] == {
        "return_1m_and_3m_positive": True,
        "sma_20_above_sma_50": False,
        "inferred_price_above_sma_50": True,
    }
    assert exactly_two.evidence["confirmation"]["state"] == "CONFIRMED_BULLISH"

    mixed = detect_regime(
        make_features(
            sma_20=100,
            sma_50=110,
            return_1m=0.11,
            return_3m=-0.01,
        ),
        RegimeThresholds(),
    )
    assert mixed.evidence["confirmation"]["bullish_agreements"] == 1
    assert mixed.evidence["confirmation"]["bearish_agreements"] == 1
    assert mixed.evidence["confirmation"]["bullish_criteria"] == {
        "return_1m_and_3m_positive": False,
        "sma_20_above_sma_50": False,
        "inferred_price_above_sma_50": True,
    }
    assert mixed.evidence["confirmation"]["bearish_criteria"] == {
        "return_1m_and_3m_negative": False,
        "sma_20_below_sma_50": True,
        "inferred_price_below_sma_50": False,
    }
    assert mixed.evidence["confirmation"]["state"] == "MIXED_OR_INSUFFICIENT"


def test_equal_direction_averages_are_neutral() -> None:
    result = detect_regime(
        make_features(sma_50=100, sma_200=100, bollinger_band_width_20=0.15),
        RegimeThresholds(),
    )

    assert result.evidence["direction"]["state"] == "NEUTRAL"
    assert result.regime == "TRANSITION"


def test_classifies_bear_only_when_direction_and_confirmation_agree() -> None:
    features = make_features(
        sma_20=90,
        sma_50=95,
        sma_200=100,
        return_1m=-0.03,
        return_3m=-0.05,
        return_6m=-0.12,
        return_12m=-0.20,
        atr_14=1,
        bollinger_band_width_20=0.15,
    )

    result = detect_regime(features, RegimeThresholds())

    assert result.regime == "BEAR"
    assert result.evidence["direction"]["state"] == "BEARISH"
    assert result.evidence["confirmation"]["state"] == "CONFIRMED_BEARISH"


def test_classifies_range_only_below_both_range_thresholds() -> None:
    thresholds = RegimeThresholds()
    result = detect_regime(
        make_features(
            return_6m=math.nextafter(0.10, 0.0),
            bollinger_band_width_20=math.nextafter(0.10, 0.0),
            sma_20=100,
            sma_50=100,
            sma_200=100,
            return_1m=0.0,
            return_3m=0.0,
            atr_14=1,
        ),
        thresholds,
    )
    on_boundary = detect_regime(
        make_features(
            return_6m=0.10,
            bollinger_band_width_20=0.05,
            sma_20=100,
            sma_50=100,
            sma_200=100,
            return_1m=0.0,
            return_3m=0.0,
            atr_14=1,
        ),
        thresholds,
    )
    on_bollinger_boundary = detect_regime(
        make_features(
            return_6m=0.09,
            bollinger_band_width_20=0.10,
            sma_20=100,
            sma_50=100,
            sma_200=100,
            return_1m=0.0,
            return_3m=0.0,
            atr_14=1,
        ),
        thresholds,
    )

    assert result.regime == "RANGE"
    assert on_boundary.regime == "TRANSITION"
    assert on_bollinger_boundary.regime == "TRANSITION"


def test_insufficient_features_result_in_transition_with_unknown_axes() -> None:
    result = detect_regime(
        make_features(
            sma_20=None,
            sma_50=None,
            sma_200=None,
            return_1m=None,
            return_3m=None,
            return_6m=None,
            return_12m=None,
            realized_volatility_20=None,
            atr_14=None,
            bollinger_band_width_20=None,
        ),
        RegimeThresholds(),
    )

    assert result.regime == "TRANSITION"
    assert result.evidence["direction"]["state"] == "UNKNOWN"
    assert result.evidence["strength"]["state"] == "UNKNOWN"
    assert result.evidence["volatility"]["state"] == "UNKNOWN"
    assert result.evidence["confirmation"]["state"] == "MIXED_OR_INSUFFICIENT"


def test_rejects_non_finite_feature_values() -> None:
    with pytest.raises(RegimeError, match="no es finita"):
        detect_regime(make_features(sma_50=float("nan")), RegimeThresholds())


@pytest.mark.parametrize(
    "values",
    [
        {"elevated_realized_volatility": 0.5, "chaotic_realized_volatility": 0.4},
        {"elevated_atr_to_sma20": 0.04, "chaotic_atr_to_sma20": 0.03},
        {"confirmation_min_agreements": 0},
    ],
)
def test_rejects_inconsistent_threshold_configuration(values: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        RegimeThresholds(**values)


def test_thresholds_are_configurable_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("AQT_REGIME_BULL_STRENGTH_RETURN_6M", "0.12")
    monkeypatch.setenv("AQT_REGIME_CONFIRMATION_MIN_AGREEMENTS", "3")

    thresholds = RegimeThresholds.from_env()

    assert thresholds.bull_strength_return_6m == 0.12
    assert thresholds.confirmation_min_agreements == 3


def test_cli_uses_market_data_engine_and_emits_json(
    tmp_path, monkeypatch, capsys
) -> None:
    from scripts import detect_regime as detect_regime_script

    class FakeProvider:
        def fetch(self, ticker: str) -> list[dict[str, object]]:
            from datetime import timedelta

            start = datetime(2024, 1, 1, tzinfo=timezone.utc)
            rows = []
            for index in range(300):
                close = 100.0 + index * 0.2
                rows.append(
                    {
                        "timestamp": start + timedelta(days=index),
                        "open": close,
                        "high": close + 0.5,
                        "low": close - 0.5,
                        "close": close,
                        "volume": 1000,
                    }
                )
            return rows

    monkeypatch.setenv("AQT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        detect_regime_script, "YahooFinanceProvider", lambda: FakeProvider()
    )

    exit_code = detect_regime_script.main(["SPY"])

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert exit_code == 0
    assert payload["ticker"] == "SPY"
    assert payload["regime"] in {
        "BULL_STRONG",
        "BULL_VOLATILE",
        "RANGE",
        "TRANSITION",
        "BEAR",
        "CHAOTIC",
    }
    assert {"metrics", "evidence", "reason_codes"} <= payload.keys()
    assert "no es una recomendación" in payload["disclaimer"]
    assert output.err == ""
