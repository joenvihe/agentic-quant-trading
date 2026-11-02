"""Application tool for explicit risk-limit decisions."""

from dataclasses import dataclass

from application.tools.types import (
    ToolResponse,
    error_response,
    resolve_trace_id,
    success_response,
)
from risk.engine import RiskEngineError, evaluate_risk
from risk.types import RiskLimits


@dataclass(frozen=True)
class RiskRequest:
    requested_weight: float
    current_exposure: float = 0.0
    limits: RiskLimits = RiskLimits()
    realized_volatility: float | None = None
    current_drawdown: float | None = None
    trace_id: str | None = None


def evaluate_risk_request(request: RiskRequest) -> ToolResponse:
    trace_id, trace_error = resolve_trace_id(request.trace_id)
    if trace_error:
        return error_response(trace_id, trace_error)
    if not isinstance(request.limits, RiskLimits):
        return error_response(trace_id, "limits must be a RiskLimits value.")
    try:
        decision = evaluate_risk(
            request.requested_weight,
            request.current_exposure,
            request.limits,
            realized_volatility=request.realized_volatility,
            current_drawdown=request.current_drawdown,
        )
    except (RiskEngineError, ValueError, TypeError) as exc:
        return error_response(trace_id, str(exc))
    warnings = (
        decision.reasons
        if decision.reasons != ("APPROVED_WITHIN_LIMITS",)
        else ()
    )
    return success_response(trace_id, decision, warnings=warnings)
