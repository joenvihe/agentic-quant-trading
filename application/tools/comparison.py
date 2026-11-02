"""Application tool for comparing existing strategy backtest results."""

from dataclasses import dataclass
import math

from application.tools.types import (
    ToolResponse,
    error_response,
    resolve_trace_id,
    success_response,
)
from backtest.types import BacktestResult
from evaluation.compare import compare_performance
from evaluation.metrics import calculate_metrics


@dataclass(frozen=True)
class ComparisonRequest:
    results: tuple[BacktestResult, ...]
    periods_per_year: int = 252
    risk_free_rate: float = 0.0
    trace_id: str | None = None


def compare_strategies(request: ComparisonRequest) -> ToolResponse:
    trace_id, trace_error = resolve_trace_id(request.trace_id)
    if trace_error:
        return error_response(trace_id, trace_error)
    if not isinstance(request.results, tuple) or any(
        not isinstance(result, BacktestResult) for result in request.results
    ):
        return error_response(
            trace_id,
            "results must be a tuple of BacktestResult values.",
        )
    if len(request.results) < 2:
        return error_response(trace_id, "At least two strategy results are required.")
    names = tuple(result.strategy_name for result in request.results)
    if any(not isinstance(name, str) or not name.strip() for name in names):
        return error_response(trace_id, "Strategy names must be non-empty strings.")
    if len(set(names)) != len(names):
        return error_response(trace_id, "Strategy names must be unique.")
    baseline = request.results[0]
    if any(not result.equity_curve for result in request.results):
        return error_response(trace_id, "Strategy results must include equity points.")
    baseline_timestamps = tuple(
        point.timestamp for point in baseline.equity_curve
    )
    for candidate in request.results[1:]:
        timestamps = tuple(point.timestamp for point in candidate.equity_curve)
        if timestamps != baseline_timestamps:
            return error_response(
                trace_id,
                "Strategy results must share the same equity-curve timestamps.",
            )
    if (
        isinstance(request.periods_per_year, bool)
        or not isinstance(request.periods_per_year, int)
        or request.periods_per_year <= 0
    ):
        return error_response(trace_id, "periods_per_year must be a positive integer.")
    if (
        isinstance(request.risk_free_rate, bool)
        or not isinstance(request.risk_free_rate, (int, float))
        or not math.isfinite(request.risk_free_rate)
    ):
        return error_response(trace_id, "risk_free_rate must be finite.")

    try:
        metrics = {
            result.strategy_name: calculate_metrics(
                result, request.periods_per_year, request.risk_free_rate
            )
            for result in request.results
        }
        comparisons = {
            result.strategy_name: compare_performance(
                result,
                baseline,
                request.periods_per_year,
                request.risk_free_rate,
            )
            for result in request.results[1:]
        }
    except (ValueError, TypeError) as exc:
        return error_response(trace_id, str(exc))
    return success_response(
        trace_id,
        {
            "baseline_strategy": baseline.strategy_name,
            "metrics": metrics,
            "comparisons_to_baseline": comparisons,
        },
    )
