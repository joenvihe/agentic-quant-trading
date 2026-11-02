"""Causal daily single-asset backtesting."""

from collections.abc import Sequence
from datetime import datetime
import math

from backtest.costs import calculate_execution_cost
from backtest.exceptions import BacktestValidationError
from backtest.types import (
    BacktestConfig,
    BacktestResult,
    EquityPoint,
    Trade,
)
from data.market_data import MarketBar, MarketData
from strategies.types import TargetPosition


def run_backtest(
    market_data: MarketData,
    target_positions: Sequence[TargetPosition],
    strategy_name: str,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Execute close-timestamped targets at the following bar's open.

    Target weights are sized from equity and close price known at the signal
    timestamp. Any final-bar target has no subsequent bar and is not executed.
    """
    settings = config or BacktestConfig()
    _validate_market_data(market_data)
    bars = market_data.bars
    if not strategy_name.strip():
        raise BacktestValidationError("strategy_name cannot be empty.")
    positions_by_timestamp = _validate_positions(
        market_data.ticker, bars, target_positions
    )

    cash = settings.initial_cash
    shares = 0.0
    trades: list[Trade] = []
    equity_curve: list[EquityPoint] = []

    for index, bar in enumerate(bars):
        if index > 0:
            signal_bar = bars[index - 1]
            position = positions_by_timestamp.get(signal_bar.timestamp)
            if position is not None:
                previous_equity = cash + shares * signal_bar.close
                target_shares = previous_equity * position.weight / signal_bar.close
                quantity = abs(target_shares - shares)
                if quantity > 0:
                    side = "BUY" if target_shares > shares else "SELL"
                    quantity = _affordable_quantity(
                        quantity, cash, bar.open, side, settings
                    )
                    if quantity > 0:
                        costs = calculate_execution_cost(
                            bar.open, quantity, side, settings
                        )
                        notional = costs.fill_price * quantity
                        if side == "BUY":
                            cash -= notional + costs.commission
                            shares += quantity
                        else:
                            cash += notional - costs.commission
                            shares -= quantity
                        if shares < 1e-12:
                            shares = 0.0
                        trades.append(
                            Trade(
                                symbol=market_data.ticker,
                                timestamp=bar.timestamp,
                                side=side,
                                quantity=quantity,
                                price=costs.fill_price,
                                commission=costs.commission,
                                slippage=costs.slippage,
                            )
                        )

        market_value = shares * bar.close
        equity = cash + market_value
        if not all(math.isfinite(value) for value in (cash, market_value, equity)):
            raise BacktestValidationError("Backtest produced a non-finite value.")
        equity_curve.append(
            EquityPoint(
                timestamp=bar.timestamp,
                equity=equity,
                cash=cash,
                market_value=market_value,
            )
        )

    return BacktestResult(
        strategy_name=strategy_name,
        equity_curve=tuple(equity_curve),
        trades=tuple(trades),
        initial_cash=settings.initial_cash,
        final_equity=equity_curve[-1].equity,
    )


def _validate_market_data(market_data: MarketData) -> None:
    if not market_data.ticker.strip():
        raise BacktestValidationError("Market data ticker cannot be empty.")
    if not market_data.bars:
        raise BacktestValidationError("Market data history cannot be empty.")

    seen: set[datetime] = set()
    previous: datetime | None = None
    for bar in market_data.bars:
        timestamp = bar.timestamp
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise BacktestValidationError("Bar timestamps must be timezone-aware.")
        if timestamp in seen:
            raise BacktestValidationError("Bar timestamps must be unique.")
        if previous is not None and timestamp <= previous:
            raise BacktestValidationError("Bar timestamps must be ordered.")
        seen.add(timestamp)
        previous = timestamp
        for field_name in ("open", "high", "low", "close"):
            price = getattr(bar, field_name)
            if not math.isfinite(price) or price <= 0:
                raise BacktestValidationError(
                    f"{field_name} prices must be finite and positive."
                )


def _validate_positions(
    ticker: str,
    bars: Sequence[MarketBar],
    target_positions: Sequence[TargetPosition],
) -> dict[datetime, TargetPosition]:
    bar_timestamps = {bar.timestamp for bar in bars}
    positions: dict[datetime, TargetPosition] = {}
    previous: datetime | None = None
    for position in target_positions:
        if position.symbol != ticker:
            raise BacktestValidationError(
                f"Position symbol {position.symbol} does not match {ticker}."
            )
        if position.timestamp not in bar_timestamps:
            raise BacktestValidationError(
                "Position timestamp must match a market-data bar."
            )
        if previous is not None and position.timestamp <= previous:
            raise BacktestValidationError(
                "Position timestamps must be ordered and unique."
            )
        if not math.isfinite(position.weight) or not 0 <= position.weight <= 1:
            raise BacktestValidationError(
                "This backtest supports long-only weights between 0 and 1."
            )
        positions[position.timestamp] = position
        previous = position.timestamp
    return positions


def _affordable_quantity(
    requested: float,
    cash: float,
    reference_price: float,
    side: str,
    config: BacktestConfig,
) -> float:
    if side == "SELL":
        return requested
    slippage_adjusted_price = reference_price * (
        1 + config.slippage_bps / 10_000
    )
    cost_per_share = slippage_adjusted_price * (
        1 + config.commission_bps / 10_000
    )
    return min(requested, max(0.0, cash / cost_per_share))
