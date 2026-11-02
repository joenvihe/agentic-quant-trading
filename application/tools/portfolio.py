"""Application tool for maximum-Sharpe portfolio optimization."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from application.tools.types import (
    ToolResponse,
    error_response,
    resolve_trace_id,
    success_response,
)
from portfolio.constraints import PortfolioConstraints
from portfolio.optimizer import MaximumSharpeOptimizer


@dataclass(frozen=True)
class PortfolioRequest:
    symbols: tuple[str, ...]
    returns_by_symbol: Mapping[str, Sequence[float]]
    constraints: PortfolioConstraints = PortfolioConstraints()
    periods_per_year: int = 252
    risk_free_rate: float = 0.0
    trace_id: str | None = None


def optimize_portfolio(request: PortfolioRequest) -> ToolResponse:
    trace_id, trace_error = resolve_trace_id(request.trace_id)
    if trace_error:
        return error_response(trace_id, trace_error)
    if not isinstance(request.constraints, PortfolioConstraints):
        return error_response(
            trace_id,
            "constraints must be a PortfolioConstraints value.",
        )
    try:
        result = MaximumSharpeOptimizer(
            constraints=request.constraints,
            periods_per_year=request.periods_per_year,
        ).optimize(
            request.symbols,
            request.returns_by_symbol,
            risk_free_rate=request.risk_free_rate,
        )
    except (ValueError, TypeError, ArithmeticError) as exc:
        return error_response(trace_id, str(exc))
    if not result.success:
        return error_response(
            trace_id,
            result.message,
            data={"optimization": result},
        )
    return success_response(trace_id, result)
