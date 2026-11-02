"""Presentation-ready table and series projections for research reports."""

from dataclasses import fields
from typing import Any

from backtest.types import BacktestResult
from evaluation.types import PerformanceMetrics
from reporting.research_report import ResearchReport


def metrics_table(metrics: PerformanceMetrics) -> tuple[dict[str, Any], ...]:
    return tuple(
        {"metric": item.name, "value": getattr(metrics, item.name)}
        for item in fields(metrics)
    )


def equity_rows(result: BacktestResult) -> tuple[dict[str, Any], ...]:
    peak = result.initial_cash
    rows = []
    for point in result.equity_curve:
        peak = max(peak, point.equity)
        drawdown = point.equity / peak - 1 if peak > 0 else None
        rows.append(
            {
                "timestamp": point.timestamp.isoformat(),
                "equity": point.equity,
                "cash": point.cash,
                "market_value": point.market_value,
                "drawdown": drawdown,
            }
        )
    return tuple(rows)


def trade_rows(result: BacktestResult) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "symbol": trade.symbol,
            "timestamp": trade.timestamp.isoformat(),
            "side": trade.side,
            "quantity": trade.quantity,
            "price": trade.price,
            "commission": trade.commission,
            "slippage": trade.slippage,
        }
        for trade in result.trades
    )


def report_tables(report: ResearchReport) -> dict[str, tuple[dict[str, Any], ...]]:
    comparison = report.benchmark_comparison
    comparison_rows = ()
    if comparison is not None:
        comparison_rows = (
            {"metric": "total_return_difference", "value": comparison.total_return_difference},
        )
    return {
        "metrics": metrics_table(report.metrics),
        "benchmark_comparison": comparison_rows,
        "equity_curve": equity_rows(report.backtest_result),
        "trades": trade_rows(report.backtest_result),
    }
