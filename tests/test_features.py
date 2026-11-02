from datetime import datetime, timedelta, timezone
import math

import pytest

from data.market_data import MarketData, normalize_market_data
from features.engine import FEATURE_NAMES, FeatureError, calculate_features


def make_market_data(
    closes: list[float], volumes: list[float] | None = None
) -> MarketData:
    volumes = volumes or [100.0] * len(closes)
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    rows = [
        {
            "timestamp": start + timedelta(days=index),
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": volumes[index],
        }
        for index, close in enumerate(closes)
    ]
    return normalize_market_data("SPY", rows)


def test_calculates_feature_families_for_latest_bar() -> None:
    closes = [100.0 + index for index in range(300)]
    result = calculate_features(make_market_data(closes))
    latest = result.rows[-1].values

    assert result.ticker == "SPY"
    assert len(result.rows) == 300
    assert latest["sma_20"] == pytest.approx(sum(closes[-20:]) / 20)
    assert latest["sma_50"] == pytest.approx(sum(closes[-50:]) / 50)
    assert latest["ema_20"] is not None
    assert latest["ema_50"] is not None
    assert latest["rsi_2"] == 100
    assert latest["rsi_14"] == 100
    assert latest["return_1m"] == pytest.approx(closes[-1] / closes[-22] - 1)
    assert latest["return_3m"] == pytest.approx(closes[-1] / closes[-64] - 1)
    assert latest["return_6m"] == pytest.approx(closes[-1] / closes[-127] - 1)
    assert latest["return_12m"] == pytest.approx(closes[-1] / closes[-253] - 1)
    assert latest["atr_14"] == pytest.approx(2.0)
    assert latest["realized_volatility_20"] is not None
    assert latest["realized_volatility_20"] > 0
    assert latest["bollinger_middle_20"] == pytest.approx(sum(closes[-20:]) / 20)
    assert latest["bollinger_upper_20"] > latest["bollinger_middle_20"]
    assert latest["bollinger_lower_20"] < latest["bollinger_middle_20"]
    assert latest["average_volume_20"] == 100
    assert latest["relative_volume_20"] == 1
    assert latest["distance_from_52w_high"] <= 0
    assert latest["rolling_drawdown_52w"] <= 0
    assert tuple(latest) == FEATURE_NAMES


def test_initial_values_are_none_until_history_is_sufficient() -> None:
    result = calculate_features(make_market_data([100.0, 101.0, 102.0]))

    latest = result.rows[-1].values
    assert latest["rsi_2"] is not None
    assert latest["sma_20"] is None
    assert latest["ema_20"] is None
    assert latest["rsi_14"] is None
    assert latest["atr_14"] is None
    assert latest["return_1m"] is None
    assert latest["bollinger_middle_20"] is None
    assert latest["average_volume_20"] is None
    assert latest["distance_from_52w_high"] is None


def test_features_handle_flat_prices_and_zero_volume_without_nan() -> None:
    result = calculate_features(make_market_data([100.0] * 300, [0.0] * 300))
    latest = result.rows[-1].values

    assert latest["rsi_2"] == 50
    assert latest["rsi_14"] == 50
    assert latest["bollinger_band_width_20"] == 0
    assert latest["relative_volume_20"] is None
    assert all(value is None or math.isfinite(value) for value in latest.values())


def test_empty_market_history_is_rejected() -> None:
    with pytest.raises(FeatureError, match="No hay barras"):
        calculate_features(MarketData(ticker="SPY", bars=()))


def test_cli_reads_local_market_data_and_prints_structured_features(
    tmp_path, monkeypatch, capsys
) -> None:
    from data.storage import save_market_data
    from scripts import analyze_features

    data_dir = tmp_path / "market_data"
    save_market_data(make_market_data([100.0 + index for index in range(260)]), data_dir)
    monkeypatch.setenv("AQT_DATA_DIR", str(tmp_path))

    exit_code = analyze_features.main(["spy"])

    output = capsys.readouterr()
    assert exit_code == 0
    assert output.err == ""
    assert '"ticker": "SPY"' in output.out
    assert '"features": {' in output.out
    assert '"sma_20":' in output.out


def test_cli_reports_missing_local_data_without_success_output(
    tmp_path, monkeypatch, capsys
) -> None:
    from scripts import analyze_features

    monkeypatch.setenv("AQT_DATA_DIR", str(tmp_path))

    exit_code = analyze_features.main(["SPY"])

    output = capsys.readouterr()
    assert exit_code == 1
    assert "Error al analizar features" in output.err
    assert output.out == ""
