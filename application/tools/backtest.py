"""Application tool for deterministic historical simulations."""

from dataclasses import dataclass

from application.tools.types import (
    ToolResponse,
    error_response,
    resolve_trace_id,
    success_response,
)
from backtest.engine import run_backtest
from backtest.exceptions import BacktestError
from backtest.types import BacktestConfig, BacktestResult
from data.market_data import MarketData
from strategies.types import TargetPosition


@dataclass(frozen=True)
class BacktestRequest:
    market_data: MarketData
    target_positions: tuple[TargetPosition, ...]
    strategy_name: str
    config: BacktestConfig = BacktestConfig()
    trace_id: str | None = None


def execute_backtest(request: BacktestRequest) -> ToolResponse:
    trace_id, trace_error = resolve_trace_id(request.trace_id)
    if trace_error:
        return error_response(trace_id, trace_error)
    if not isinstance(request.strategy_name, str) or not request.strategy_name.strip():
        return error_response(trace_id, "strategy_name cannot be empty.")
    if not isinstance(request.market_data, MarketData):
        return error_response(trace_id, "market_data must be normalized MarketData.")
    if not isinstance(request.config, BacktestConfig):
        return error_response(trace_id, "config must be a BacktestConfig.")
    if not isinstance(request.target_positions, tuple) or any(
        not isinstance(position, TargetPosition)
        for position in request.target_positions
    ):
        return error_response(
            trace_id,
            "target_positions must be a tuple of TargetPosition values.",
        )
    try:
        result: BacktestResult = run_backtest(
            request.market_data,
            request.target_positions,
            request.strategy_name,
            request.config,
        )
    except (BacktestError, ValueError, TypeError) as exc:
        return error_response(trace_id, str(exc))
    return success_response(trace_id, result)
