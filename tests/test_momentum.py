from dataclasses import fields
from datetime import datetime, timedelta, timezone
import math

import pytest

from config.momentum import MomentumWeights
from data.market_data import MarketData, normalize_market_data
from factors.momentum import MomentumRankingError, rank_momentum
from features.engine import FeatureRow, FeatureSeries, calculate_features


def feature_series(
    ticker: str, returns: tuple[float, float, float, float]
) -> FeatureSeries:
    values = {
        "return_1m": returns[0],
        "return_3m": returns[1],
        "return_6m": returns[2],
        "return_12m": returns[3],
    }
    return FeatureSeries(
        ticker=ticker,
        rows=(
            FeatureRow(
                timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
                values=values,
            ),
        ),
    )


def market_data(ticker: str, count: int = 260) -> MarketData:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(count):
        close = 100.0 + index * 0.25
        rows.append(
            {
                "timestamp": start + timedelta(days=index),
                "open": close,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": 1000 + index,
            }
        )
    return normalize_market_data(ticker, rows)


def test_ranks_all_momentum_horizons_and_calculates_absolute_momentum() -> None:
    series = {
        "SPY": feature_series("SPY", (0.01, 0.03, 0.06, 0.12)),
        "QQQ": feature_series("QQQ", (0.02, 0.04, 0.08, 0.16)),
        "IWM": feature_series("IWM", (-0.01, 0.01, 0.02, -0.02)),
        "DIA": feature_series("DIA", (0.03, 0.02, 0.01, 0.04)),
    }

    ranking = rank_momentum(series, MomentumWeights())

    assert [item.ticker for item in ranking] == ["QQQ", "SPY", "DIA", "IWM"]
    assert [item.rank for item in ranking] == [1, 2, 3, 4]
    assert ranking[0].momentum_1m == 0.02
    assert ranking[0].momentum_12m == 0.16
    assert ranking[0].absolute_momentum
    assert not ranking[-1].absolute_momentum
    assert ranking[0].composite_score == pytest.approx(91.66666666666666)
    assert ranking[-1].composite_score == pytest.approx(8.333333333333334)
    assert ranking[0].percentile_rank == 100
    assert ranking[-1].percentile_rank == 0
    assert ranking[0].relative_momentum["1m"] == pytest.approx(200 / 3)
    assert ranking[0].relative_momentum["3m"] == 100
    assert ranking[0].relative_momentum["6m"] == 100
    assert ranking[0].relative_momentum["12m"] == 100
    assert {field.name for field in fields(ranking[0])} == {
        "rank",
        "ticker",
        "momentum_1m",
        "momentum_3m",
        "momentum_6m",
        "momentum_12m",
        "absolute_momentum",
        "relative_momentum",
        "percentile_rank",
        "composite_score",
    }


def test_composite_weights_are_applied_from_configuration() -> None:
    series = {
        "A": feature_series("A", (0.01, 0.03, 0.06, 0.12)),
        "B": feature_series("B", (0.02, 0.02, 0.02, 0.02)),
    }
    weights = MomentumWeights(weight_1m=1, weight_3m=0, weight_6m=0, weight_12m=0)

    ranking = rank_momentum(series, weights)

    assert ranking[0].ticker == "B"
    assert ranking[0].composite_score == 100
    assert ranking[1].composite_score == 0


def test_percentile_ranks_assign_average_rank_to_ties() -> None:
    series = {
        "A": feature_series("A", (0.0, 0.0, 0.0, 0.0)),
        "B": feature_series("B", (0.0, 0.0, 0.0, 0.0)),
        "C": feature_series("C", (0.1, 0.1, 0.1, 0.1)),
    }

    ranking = rank_momentum(series, MomentumWeights())
    by_ticker = {item.ticker: item for item in ranking}

    assert by_ticker["A"].composite_score == by_ticker["B"].composite_score
    assert by_ticker["A"].percentile_rank == 25
    assert by_ticker["B"].percentile_rank == 25
    assert by_ticker["C"].percentile_rank == 100


@pytest.mark.parametrize(
    "weights",
    [
        {"weight_1m": -1},
        {"weight_1m": float("nan")},
        {"weight_1m": float("inf")},
        {"weight_1m": 0, "weight_3m": 0, "weight_6m": 0, "weight_12m": 0},
    ],
)
def test_rejects_invalid_weights(weights: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        MomentumWeights(**weights)


def test_weights_can_be_configured_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("AQT_MOMENTUM_WEIGHT_1M", "2")
    monkeypatch.setenv("AQT_MOMENTUM_WEIGHT_3M", "3")
    monkeypatch.setenv("AQT_MOMENTUM_WEIGHT_6M", "4")
    monkeypatch.setenv("AQT_MOMENTUM_WEIGHT_12M", "5")

    weights = MomentumWeights.from_env()

    assert weights == MomentumWeights(2, 3, 4, 5)


def test_rejects_empty_universe_and_insufficient_history() -> None:
    with pytest.raises(MomentumRankingError, match="vacío"):
        rank_momentum({}, MomentumWeights())

    insufficient = calculate_features(market_data("SPY", count=252))
    with pytest.raises(MomentumRankingError, match="historial insuficiente"):
        rank_momentum({"SPY": insufficient}, MomentumWeights())


def test_rejects_non_finite_return_values() -> None:
    invalid = feature_series("SPY", (0.1, 0.2, 0.3, math.inf))
    with pytest.raises(MomentumRankingError, match="finito"):
        rank_momentum({"SPY": invalid}, MomentumWeights())


def test_cli_fetches_through_market_data_engine_and_prints_ranking(
    tmp_path, monkeypatch, capsys
) -> None:
    from scripts import rank_momentum as rank_momentum_script

    class FakeProvider:
        def __init__(self) -> None:
            self.requested: list[str] = []

        def fetch(self, ticker: str) -> list[dict[str, object]]:
            self.requested.append(ticker)
            return [
                {
                    "timestamp": bar.timestamp,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
                for bar in market_data(ticker).bars
            ]

    provider = FakeProvider()
    monkeypatch.setenv("AQT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        rank_momentum_script, "YahooFinanceProvider", lambda: provider
    )

    exit_code = rank_momentum_script.main(["SPY", "QQQ", "IWM", "DIA"])

    output = capsys.readouterr()
    assert exit_code == 0
    assert provider.requested == ["SPY", "QQQ", "IWM", "DIA"]
    assert "Rank | Ticker | 1M | 3M | 6M | 12M | Score" in output.out
    assert "Ranking cuantitativo; no es una recomendación financiera." in output.out
    assert output.err == ""


def test_cli_rejects_duplicate_tickers_without_downloading(
    monkeypatch, capsys
) -> None:
    from scripts import rank_momentum as rank_momentum_script

    monkeypatch.setattr(
        rank_momentum_script,
        "YahooFinanceProvider",
        lambda: pytest.fail("No debe iniciar descargas con tickers duplicados."),
    )

    exit_code = rank_momentum_script.main(["SPY", "spy"])

    output = capsys.readouterr()
    assert exit_code == 1
    assert "tickers duplicados" in output.err
    assert output.out == ""
