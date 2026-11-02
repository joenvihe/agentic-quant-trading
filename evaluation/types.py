"""Typed performance-analysis results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return: float | None
    cagr: float | None
    annualized_volatility: float | None
    sharpe: float | None
    sortino: float | None
    maximum_drawdown: float | None
    calmar: float | None
    win_rate: float | None
    profit_factor: float | None
    number_of_trades: int
