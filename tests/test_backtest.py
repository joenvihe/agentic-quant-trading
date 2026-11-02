from dataclasses import replace
from datetime import datetime, timedelta, timezone
import math

import pytest

from backtest import (
    BacktestConfig,
    BacktestResult,
    BacktestValidationError,
    EquityPoint,
    Trade,
    run_backtest,
)
from data.market_data import MarketBar, MarketData
from evaluation import (
    buy_and_hold_benchmark,
    calculate_metrics,
    compare_performance,
)
from strategies.types import TargetPosition


START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def market_data(
    prices: tuple[float, ...], opens: tuple[float, ...] | None = None
) -> MarketData:
    if opens is None:
        opens = prices
    bars = tuple(
        MarketBar(
            timestamp=START + timedelta(days=index),
            open=opening,
            high=max(opening, close),
            low=min(opening, close),
            close=close,
            volume=1000.0,
        )
        for index, (opening, close) in enumerate(zip(opens, prices))
    )
    return MarketData("SPY", bars)


def position(index: int, weight: float) -> TargetPosition:
    return TargetPosition(
        symbol="SPY",
        timestamp=START + timedelta(days=index),
        weight=weight,
        reason="test",
    )


def test_always_flat_strategy_has_no_trades_and_flat_equity() -> None:
    data = market_data((100.0, 110.0, 90.0))

    result = run_backtest(
        data,
        tuple(position(index, 0.0) for index in range(3)),
        "always_flat",
        BacktestConfig(initial_cash=1000),
    )

    assert result.trades == ()
    assert [point.equity for point in result.equity_curve] == [1000, 1000, 1000]
    metrics = calculate_metrics(result)
    assert metrics.total_return == 0
    assert metrics.annualized_volatility is None
    assert metrics.sharpe is None
    assert metrics.sortino is None
    assert metrics.number_of_trades == 0
    assert metrics.win_rate is None
    assert metrics.profit_factor is None


def test_position_from_close_t_is_executed_at_open_t_plus_one() -> None:
    data = market_data((100.0, 100.0, 120.0), opens=(100.0, 105.0, 115.0))

    result = run_backtest(
        data,
        (position(0, 1.0),),
        "causal_entry",
        BacktestConfig(initial_cash=1000),
    )

    assert len(result.trades) == 1
    assert result.trades[0].timestamp == data.bars[1].timestamp
    assert result.trades[0].price == 105.0
    assert result.equity_curve[0].market_value == 0
    assert result.equity_curve[1].market_value == pytest.approx(
        result.trades[0].quantity * data.bars[1].close
    )


def test_entry_and_exit_positions_are_filled_one_bar_later() -> None:
    data = market_data(
        (100.0, 110.0, 120.0, 115.0),
        opens=(100.0, 100.0, 110.0, 120.0),
    )

    result = run_backtest(
        data,
        (position(0, 1.0), position(1, 0.0)),
        "entry_exit",
        BacktestConfig(initial_cash=1000),
    )

    assert [trade.side for trade in result.trades] == ["BUY", "SELL"]
    assert [trade.timestamp for trade in result.trades] == [
        data.bars[1].timestamp,
        data.bars[2].timestamp,
    ]
    assert result.equity_curve[-1].cash == pytest.approx(1100)
    assert result.equity_curve[-1].market_value == 0


def test_commission_and_slippage_reduce_equity_and_are_recorded() -> None:
    data = market_data((100.0, 100.0, 100.0))
    positions = (position(0, 1.0), position(1, 0.0))

    no_costs = run_backtest(
        data, positions, "no_costs", BacktestConfig(initial_cash=1000)
    )
    with_costs = run_backtest(
        data,
        positions,
        "costs",
        BacktestConfig(
            initial_cash=1000,
            commission_bps=10,
            slippage_bps=20,
        ),
    )

    assert with_costs.final_equity < no_costs.final_equity
    assert all(trade.commission > 0 for trade in with_costs.trades)
    assert all(trade.slippage > 0 for trade in with_costs.trades)
    assert with_costs.trades[0].price > 100
    assert with_costs.trades[1].price < 100


@pytest.mark.parametrize("initial_cash", [0, -1, math.nan, math.inf, True])
def test_rejects_invalid_initial_capital(initial_cash: float) -> None:
    with pytest.raises(ValueError, match="initial_cash"):
        BacktestConfig(initial_cash=initial_cash)


@pytest.mark.parametrize("price", [0.0, -1.0, math.nan, math.inf])
def test_rejects_invalid_market_prices(price: float) -> None:
    bad_bar = replace(
        market_data((100.0, 100.0)).bars[0],
        close=price,
    )
    invalid_data = MarketData(
        "SPY",
        (bad_bar, market_data((100.0, 100.0)).bars[1]),
    )

    with pytest.raises(BacktestValidationError, match="close prices"):
        run_backtest(invalid_data, (), "invalid_prices")


def test_rejects_unordered_or_duplicate_market_timestamps() -> None:
    bars = market_data((100.0, 110.0, 120.0)).bars
    with pytest.raises(BacktestValidationError, match="ordered"):
        run_backtest(MarketData("SPY", (bars[1], bars[0])), (), "unordered")
    with pytest.raises(BacktestValidationError, match="unique"):
        run_backtest(MarketData("SPY", (bars[0], bars[0])), (), "duplicate")


@pytest.mark.parametrize("weight", [-0.01])
def test_rejects_invalid_long_only_positions(weight: float) -> None:
    with pytest.raises(BacktestValidationError, match="long-only"):
        run_backtest(
            market_data((100.0, 100.0)),
            (position(0, weight),),
            "invalid_position",
        )


@pytest.mark.parametrize("weight", [1.01, math.nan, math.inf])
def test_target_position_rejects_weights_outside_its_contract(weight: float) -> None:
    with pytest.raises(ValueError, match="weight"):
        position(0, weight)


def test_rejects_duplicate_or_unknown_position_timestamps() -> None:
    data = market_data((100.0, 100.0, 100.0))
    with pytest.raises(BacktestValidationError, match="unique"):
        run_backtest(data, (position(0, 1.0), position(0, 0.0)), "duplicate")
    unknown = TargetPosition("SPY", START - timedelta(days=1), 1.0, "unknown")
    with pytest.raises(BacktestValidationError, match="match a market-data bar"):
        run_backtest(data, (unknown,), "unknown_time")


def test_buy_and_hold_benchmark_is_deterministic_and_long() -> None:
    data = market_data((100.0, 110.0, 120.0), opens=(100.0, 100.0, 110.0))
    config = BacktestConfig(initial_cash=1000)

    first = buy_and_hold_benchmark(data, config)
    second = buy_and_hold_benchmark(data, config)

    assert first == second
    assert first.strategy_name == "buy_and_hold"
    assert len(first.trades) == 1
    assert first.trades[0].side == "BUY"
    assert first.final_equity == pytest.approx(1200)


def test_metrics_calculate_known_total_return_cagr_and_drawdown() -> None:
    result = BacktestResult(
        strategy_name="known",
        equity_curve=(
            EquityPoint(START, 100.0, 100.0, 0.0),
            EquityPoint(START + timedelta(days=1), 120.0, 120.0, 0.0),
            EquityPoint(START + timedelta(days=2), 90.0, 90.0, 0.0),
        ),
        trades=(),
        initial_cash=100.0,
        final_equity=90.0,
    )

    metrics = calculate_metrics(result, periods_per_year=2)

    assert metrics.total_return == pytest.approx(-0.1)
    assert metrics.cagr == pytest.approx(0.9**1 - 1)
    assert metrics.maximum_drawdown == pytest.approx(-0.25)
    assert metrics.calmar == pytest.approx(-0.4)


def test_metrics_return_none_for_undefined_ratios_and_apply_risk_free_rate() -> None:
    flat = run_backtest(
        market_data((100.0, 100.0, 100.0)),
        (),
        "flat",
        BacktestConfig(initial_cash=1000),
    )
    metrics = calculate_metrics(flat, periods_per_year=12)
    risk_adjusted = calculate_metrics(
        flat, periods_per_year=12, risk_free_rate=0.03
    )

    assert metrics.sharpe is None
    assert metrics.sortino is None
    assert metrics.calmar is None
    assert risk_adjusted.sharpe is None
    assert risk_adjusted.sortino == pytest.approx(-math.sqrt(12))
    with pytest.raises(ValueError, match="periods_per_year"):
        calculate_metrics(flat, periods_per_year=0)


def test_metrics_count_round_trip_and_compare_to_benchmark() -> None:
    data = market_data((100.0, 100.0, 120.0, 120.0), opens=(100.0, 100.0, 120.0, 120.0))
    config = BacktestConfig(initial_cash=1000)
    strategy = run_backtest(
        data, (position(0, 1.0), position(1, 0.0)), "strategy", config
    )
    benchmark = buy_and_hold_benchmark(data, config)

    strategy_metrics = calculate_metrics(strategy)
    comparison = compare_performance(strategy, benchmark)

    assert strategy_metrics.number_of_trades == 2
    assert strategy_metrics.win_rate == 1.0
    assert strategy_metrics.profit_factor is None
    assert comparison.strategy == strategy_metrics
    assert comparison.benchmark.total_return is not None
    assert comparison.total_return_difference is not None


def test_profit_factor_and_win_rate_use_realized_round_trips() -> None:
    trades = (
        Trade("SPY", START, "BUY", 1.0, 100.0, 0.0, 0.0),
        Trade("SPY", START + timedelta(days=1), "SELL", 1.0, 110.0, 0.0, 0.0),
        Trade("SPY", START + timedelta(days=2), "BUY", 1.0, 110.0, 0.0, 0.0),
        Trade("SPY", START + timedelta(days=3), "SELL", 1.0, 100.0, 0.0, 0.0),
    )
    result = BacktestResult(
        strategy_name="wins_and_losses",
        equity_curve=(
            EquityPoint(START, 1000.0, 1000.0, 0.0),
            EquityPoint(START + timedelta(days=1), 1000.0, 1000.0, 0.0),
        ),
        trades=trades,
        initial_cash=1000.0,
        final_equity=1000.0,
    )

    metrics = calculate_metrics(result)

    assert metrics.win_rate == 0.5
    assert metrics.profit_factor == 1.0
    assert metrics.number_of_trades == 4
