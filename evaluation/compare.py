"""Comparison between a strategy run and the buy-and-hold benchmark."""

from dataclasses import dataclass

from backtest.types import BacktestResult
from evaluation.metrics import calculate_metrics
from evaluation.types import PerformanceMetrics


@dataclass(frozen=True)
class PerformanceComparison:
    strategy: PerformanceMetrics
    benchmark: PerformanceMetrics
    total_return_difference: float | None


def compare_performance(
    strategy_result: BacktestResult,
    benchmark_result: BacktestResult,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
) -> PerformanceComparison:
    strategy_metrics = calculate_metrics(
        strategy_result, periods_per_year, risk_free_rate
    )
    benchmark_metrics = calculate_metrics(
        benchmark_result, periods_per_year, risk_free_rate
    )
    difference = None
    if (
        strategy_metrics.total_return is not None
        and benchmark_metrics.total_return is not None
    ):
        difference = strategy_metrics.total_return - benchmark_metrics.total_return
    return PerformanceComparison(
        strategy=strategy_metrics,
        benchmark=benchmark_metrics,
        total_return_difference=difference,
    )
