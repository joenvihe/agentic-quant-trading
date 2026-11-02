"""Research report aggregate assembled from already-computed results."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from backtest.types import BacktestResult
from evaluation.compare import PerformanceComparison
from evaluation.types import PerformanceMetrics


@dataclass(frozen=True)
class ResearchReport:
    backtest_result: BacktestResult
    metrics: PerformanceMetrics
    benchmark_comparison: PerformanceComparison | None
    configuration: Mapping[str, Any]
    strategy_parameters: Mapping[str, Any]
    symbols: tuple[str, ...]
    warnings: tuple[str, ...]
    output_files: tuple[str, ...] = ()

    @property
    def strategy_name(self) -> str:
        return self.backtest_result.strategy_name

    @property
    def start(self) -> datetime | None:
        return (
            self.backtest_result.equity_curve[0].timestamp
            if self.backtest_result.equity_curve
            else None
        )

    @property
    def end(self) -> datetime | None:
        return (
            self.backtest_result.equity_curve[-1].timestamp
            if self.backtest_result.equity_curve
            else None
        )


def build_research_report(
    backtest_result: BacktestResult,
    metrics: PerformanceMetrics,
    benchmark_comparison: PerformanceComparison | None = None,
    *,
    configuration: Mapping[str, Any] | None = None,
    strategy_parameters: Mapping[str, Any] | None = None,
    symbols: tuple[str, ...] | list[str] | None = None,
    warnings: tuple[str, ...] | list[str] = (),
    output_files: tuple[str, ...] | list[str] = (),
) -> ResearchReport:
    if symbols is None:
        inferred = tuple(dict.fromkeys(trade.symbol for trade in backtest_result.trades))
        symbols = inferred
    return ResearchReport(
        backtest_result=backtest_result,
        metrics=metrics,
        benchmark_comparison=benchmark_comparison,
        configuration=dict(configuration or {}),
        strategy_parameters=dict(strategy_parameters or {}),
        symbols=tuple(symbols),
        warnings=tuple(warnings),
        output_files=tuple(output_files),
    )
