"""Deterministic performance metrics from an equity curve and trades."""

from collections.abc import Sequence
import math
from statistics import fmean, pstdev

from backtest.types import BacktestResult, EquityPoint, Trade
from evaluation.types import PerformanceMetrics


def calculate_metrics(
    result: BacktestResult,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
) -> PerformanceMetrics:
    if (
        isinstance(periods_per_year, bool)
        or not isinstance(periods_per_year, int)
        or periods_per_year <= 0
    ):
        raise ValueError("periods_per_year must be a positive integer.")
    if not math.isfinite(risk_free_rate):
        raise ValueError("risk_free_rate must be finite.")

    curve = result.equity_curve
    returns = _period_returns(curve)
    total_return = _safe_ratio(result.final_equity, result.initial_cash)
    if total_return is not None:
        total_return -= 1

    periods = len(curve) - 1
    cagr = None
    if periods > 0 and result.initial_cash > 0 and result.final_equity > 0:
        try:
            cagr = (result.final_equity / result.initial_cash) ** (
                periods_per_year / periods
            ) - 1
        except OverflowError:
            cagr = None
        else:
            if not math.isfinite(cagr):
                cagr = None

    excess_returns = [value - risk_free_rate / periods_per_year for value in returns]
    volatility = (
        pstdev(returns) * math.sqrt(periods_per_year) if len(returns) > 1 else None
    )
    if volatility is not None and (not math.isfinite(volatility) or volatility == 0):
        volatility = None

    sharpe = None
    if len(excess_returns) > 1:
        standard_deviation = pstdev(excess_returns)
        if standard_deviation > 0:
            sharpe = fmean(excess_returns) / standard_deviation * math.sqrt(
                periods_per_year
            )
            if not math.isfinite(sharpe):
                sharpe = None

    downside = [min(value, 0.0) for value in excess_returns]
    downside_deviation = (
        math.sqrt(fmean(value * value for value in downside))
        if downside
        else 0.0
    )
    sortino = None
    if downside_deviation > 0:
        sortino = fmean(excess_returns) / downside_deviation * math.sqrt(
            periods_per_year
        )
        if not math.isfinite(sortino):
            sortino = None

    drawdown = _maximum_drawdown(curve, result.initial_cash)
    calmar = None
    if drawdown is not None and drawdown < 0 and cagr is not None:
        calmar = cagr / abs(drawdown)
        if not math.isfinite(calmar):
            calmar = None

    closed_pnls = _closed_trade_pnls(result.trades)
    win_rate = (
        sum(pnl > 0 for pnl in closed_pnls) / len(closed_pnls)
        if closed_pnls
        else None
    )
    gross_profit = sum(pnl for pnl in closed_pnls if pnl > 0)
    gross_loss = -sum(pnl for pnl in closed_pnls if pnl < 0)
    profit_factor = None
    if gross_loss > 0:
        candidate = gross_profit / gross_loss
        if math.isfinite(candidate):
            profit_factor = candidate

    return PerformanceMetrics(
        total_return=_finite_or_none(total_return),
        cagr=_finite_or_none(cagr),
        annualized_volatility=_finite_or_none(volatility),
        sharpe=_finite_or_none(sharpe),
        sortino=_finite_or_none(sortino),
        maximum_drawdown=drawdown,
        calmar=_finite_or_none(calmar),
        win_rate=_finite_or_none(win_rate),
        profit_factor=_finite_or_none(profit_factor),
        number_of_trades=len(result.trades),
    )


def _period_returns(curve: Sequence[EquityPoint]) -> list[float]:
    returns: list[float] = []
    for previous, current in zip(curve, curve[1:]):
        if previous.equity <= 0:
            return []
        value = current.equity / previous.equity - 1
        if not math.isfinite(value):
            return []
        returns.append(value)
    return returns


def _maximum_drawdown(
    curve: Sequence[EquityPoint], initial_cash: float
) -> float | None:
    if not curve:
        return None
    peak = initial_cash
    maximum = 0.0
    for point in curve:
        if not math.isfinite(point.equity) or point.equity < 0:
            return None
        peak = max(peak, point.equity)
        if peak > 0:
            maximum = min(maximum, point.equity / peak - 1)
    return maximum


def _closed_trade_pnls(trades: Sequence[Trade]) -> list[float]:
    shares = 0.0
    average_cost = 0.0
    realized: list[float] = []
    for trade in trades:
        if trade.side == "BUY":
            total_cost = trade.price * trade.quantity + trade.commission
            new_shares = shares + trade.quantity
            average_cost = (
                (shares * average_cost + total_cost) / new_shares
                if new_shares > 0
                else 0.0
            )
            shares = new_shares
        elif trade.side == "SELL":
            closed_quantity = min(shares, trade.quantity)
            if closed_quantity > 0:
                net_proceeds = (
                    trade.price * trade.quantity - trade.commission
                ) * (closed_quantity / trade.quantity)
                realized.append(net_proceeds - average_cost * closed_quantity)
                shares -= closed_quantity
                if shares < 1e-12:
                    shares = 0.0
                    average_cost = 0.0
    return realized


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    value = numerator / denominator
    return value if math.isfinite(value) else None


def _finite_or_none(value: float | None) -> float | None:
    return value if value is not None and math.isfinite(value) else None
