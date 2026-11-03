from datetime import datetime, timedelta, timezone
import math
from types import SimpleNamespace
from typing import cast

import pytest

import evaluation.walk_forward as walk_forward_module
from backtest.types import BacktestResult, EquityPoint
from data.market_data import MarketBar, MarketData
from evaluation import (
    TemporalSplitError,
    TimeWindow,
    generate_time_splits,
    run_walk_forward,
    summarize_robustness,
)


START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def market_data(count: int = 10) -> MarketData:
    bars = tuple(
        MarketBar(
            timestamp=START + timedelta(days=index),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1000.0,
        )
        for index in range(count)
    )
    return MarketData("SPY", bars)


def fake_backtest(data: MarketData, parameters: dict[str, float]) -> BacktestResult:
    points = tuple(
        EquityPoint(
            timestamp=bar.timestamp,
            equity=100.0 + parameters["edge"] * index,
            cash=100.0 + parameters["edge"] * index,
            market_value=0.0,
        )
        for index, bar in enumerate(data.bars)
    )
    return BacktestResult(
        strategy_name="fake",
        equity_curve=points,
        trades=(),
        initial_cash=100.0,
        final_equity=points[-1].equity,
    )


def test_time_windows_are_strictly_chronological_for_expanding_and_rolling() -> None:
    data = market_data()

    expanding = generate_time_splits(data, 3, 2, mode="expanding")
    rolling = generate_time_splits(data, 3, 2, step_size=2, mode="rolling")

    assert expanding[0] == TimeWindow(
        train_start=data.bars[0].timestamp,
        train_end=data.bars[2].timestamp,
        test_start=data.bars[3].timestamp,
        test_end=data.bars[4].timestamp,
    )
    assert expanding[1].train_start == data.bars[0].timestamp
    assert rolling[1].train_start == data.bars[2].timestamp
    assert all(window.train_end < window.test_start for window in expanding)
    assert all(window.train_end < window.test_start for window in rolling)


def test_insufficient_history_and_invalid_time_window_are_rejected() -> None:
    with pytest.raises(TemporalSplitError, match="Insufficient history"):
        generate_time_splits(market_data(4), 3, 2)

    with pytest.raises(ValueError, match="train_start"):
        TimeWindow(
            START,
            START + timedelta(days=2),
            START + timedelta(days=2),
            START + timedelta(days=3),
        )


def test_splits_reject_unordered_market_data() -> None:
    bars = market_data(5).bars

    with pytest.raises(TemporalSplitError, match="ordered"):
        generate_time_splits(MarketData("SPY", (bars[1], bars[0])), 1, 1)


def test_walk_forward_selects_on_train_and_evaluates_only_selected_on_test() -> None:
    data = market_data(8)
    candidates = ({"edge": 1.0}, {"edge": 2.0})
    calls: list[tuple[tuple[datetime, ...], float]] = []

    def evaluator(
        window_data: MarketData, parameters: dict[str, float]
    ) -> BacktestResult:
        calls.append(
            (
                tuple(bar.timestamp for bar in window_data.bars),
                parameters["edge"],
            )
        )
        return fake_backtest(window_data, parameters)

    results = run_walk_forward(
        data,
        candidates,
        evaluator,
        train_size=3,
        test_size=2,
        metric_name="total_return",
    )

    first = results[0]
    assert first.selected_parameters == {"edge": 2.0}
    assert first.in_sample_metrics is not None
    assert first.in_sample_metrics.total_return == pytest.approx(0.04)
    assert first.out_of_sample_metrics is not None
    assert first.out_of_sample_metrics.total_return == pytest.approx(0.02)
    assert calls[:2] == [
        (tuple(bar.timestamp for bar in data.bars[:3]), 1.0),
        (tuple(bar.timestamp for bar in data.bars[:3]), 2.0),
    ]
    assert calls[2] == (
        tuple(bar.timestamp for bar in data.bars[3:5]),
        2.0,
    )
    assert all(
        max(timestamps) <= first.window.train_end
        for timestamps, _ in calls[:2]
    )
    assert min(calls[2][0]) >= first.window.test_start


def test_walk_forward_returns_warning_if_train_metric_is_undefined() -> None:
    data = market_data(5)

    results = run_walk_forward(
        data,
        ({"edge": 0.0},),
        fake_backtest,
        train_size=3,
        test_size=2,
        metric_name="sharpe",
    )

    assert results[0].selected_parameters is None
    assert results[0].in_sample_metrics is None
    assert results[0].out_of_sample_metrics is None
    assert (
        "In-sample sharpe is undefined; no parameters were selected."
        in results[0].warnings
    )


@pytest.mark.parametrize("invalid_metric", [None, float("nan"), float("inf")])
def test_walk_forward_does_not_evaluate_oos_without_valid_train_metric(
    monkeypatch, invalid_metric: float | None
) -> None:
    data = market_data(5)
    calls: list[tuple[datetime, ...]] = []
    monkeypatch.setattr(
        walk_forward_module,
        "calculate_metrics",
        lambda *args, **kwargs: SimpleNamespace(sharpe=invalid_metric),
    )

    def evaluator(window_data: MarketData, parameters: dict[str, float]):
        calls.append(tuple(bar.timestamp for bar in window_data.bars))
        return fake_backtest(window_data, parameters)

    candidates = ({"edge": 1.0}, {"edge": 2.0})
    result = run_walk_forward(
        data,
        candidates,
        evaluator,
        train_size=3,
        test_size=2,
        metric_name="sharpe",
    )[0]

    assert result.selected_parameters is None
    assert result.in_sample_metrics is None
    assert result.out_of_sample_metrics is None
    assert result.warnings == (
        "In-sample sharpe is undefined; no parameters were selected.",
    )
    assert calls == [tuple(bar.timestamp for bar in data.bars[:3])] * len(candidates)


def test_walk_forward_skips_invalid_candidates_and_breaks_ties_by_input_order(
    monkeypatch,
) -> None:
    data = market_data(5)
    metrics = iter(
        (
            float("nan"),
            2.0,
            2.0,
            1.5,
        )
    )
    calls: list[tuple[datetime, ...]] = []
    monkeypatch.setattr(
        walk_forward_module,
        "calculate_metrics",
        lambda *args, **kwargs: SimpleNamespace(sharpe=next(metrics)),
    )

    def evaluator(window_data: MarketData, parameters: dict[str, float]):
        calls.append(tuple(bar.timestamp for bar in window_data.bars))
        return fake_backtest(window_data, parameters)

    first_valid = {"edge": 2.0}
    second_valid = {"edge": 3.0}
    result = run_walk_forward(
        data,
        ({"edge": 1.0}, first_valid, second_valid),
        evaluator,
        train_size=3,
        test_size=2,
        metric_name="sharpe",
    )[0]

    assert result.selected_parameters is first_valid
    assert result.in_sample_metrics is not None
    assert result.out_of_sample_metrics is not None
    assert result.in_sample_metrics.sharpe == 2.0
    assert result.out_of_sample_metrics.sharpe == 1.5
    assert result.warnings == ()
    assert len(calls) == 4
    assert calls[-1] == tuple(bar.timestamp for bar in data.bars[3:])


@pytest.mark.parametrize("oos_metric", [None, float("nan"), float("inf")])
def test_walk_forward_warns_for_undefined_oos_metric_after_valid_selection(
    monkeypatch, oos_metric: float | None
) -> None:
    data = market_data(5)
    metrics = iter((1.0, oos_metric))
    monkeypatch.setattr(
        walk_forward_module,
        "calculate_metrics",
        lambda *args, **kwargs: SimpleNamespace(sharpe=next(metrics)),
    )

    result = run_walk_forward(
        data,
        ({"edge": 1.0},),
        fake_backtest,
        train_size=3,
        test_size=2,
        metric_name="sharpe",
    )[0]

    assert result.selected_parameters == {"edge": 1.0}
    assert result.in_sample_metrics is not None
    assert result.out_of_sample_metrics is not None
    assert result.in_sample_metrics.sharpe == 1.0
    observed_oos_metric = result.out_of_sample_metrics.sharpe
    if oos_metric is None:
        assert observed_oos_metric is None
    elif math.isnan(oos_metric):
        assert isinstance(observed_oos_metric, float)
        assert math.isnan(observed_oos_metric)
    else:
        assert observed_oos_metric == oos_metric
    assert result.warnings == (
        "Out-of-sample sharpe is undefined for this window.",
    )


def test_walk_forward_rejects_empty_candidates_and_unknown_metrics() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        run_walk_forward(market_data(), (), fake_backtest, train_size=3, test_size=2)
    with pytest.raises(ValueError, match="Unknown performance metric"):
        run_walk_forward(
            market_data(),
            ({"edge": 1.0},),
            fake_backtest,
            train_size=3,
            test_size=2,
            metric_name="unknown",
        )
    with pytest.raises(ValueError, match="maximize_metric"):
        run_walk_forward(
            market_data(),
            ({"edge": 1.0},),
            fake_backtest,
            train_size=3,
            test_size=2,
            maximize_metric=cast(bool, "yes"),
        )


def test_walk_forward_can_minimize_train_metric() -> None:
    data = market_data(5)
    candidates = ({"edge": 2.0}, {"edge": 1.0})

    results = run_walk_forward(
        data,
        candidates,
        fake_backtest,
        train_size=3,
        test_size=2,
        metric_name="total_return",
        maximize_metric=False,
    )

    assert results[0].selected_parameters == {"edge": 1.0}
    assert not results[0].maximize_metric


def test_robustness_summary_reports_oos_consistency() -> None:
    results = run_walk_forward(
        market_data(8),
        ({"edge": 2.0},),
        fake_backtest,
        train_size=3,
        test_size=2,
        metric_name="total_return",
    )

    summary = summarize_robustness(results)

    assert summary.total_folds == 2
    assert summary.valid_folds == 2
    assert summary.mean_out_of_sample_return == pytest.approx(0.02)
    assert summary.return_volatility == 0
    assert summary.positive_return_fraction == 1
