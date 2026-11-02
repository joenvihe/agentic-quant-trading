"""Pure risk decision engine; does not execute or alter strategy positions."""

import math
from numbers import Real

from risk.drawdown import drawdown_breached
from risk.sizing import calculate_approved_weight
from risk.types import RiskDecision, RiskLimits


class RiskEngineError(ValueError):
    """Raised when risk inputs are invalid."""


def evaluate_risk(
    requested_weight: float,
    current_exposure: float,
    limits: RiskLimits,
    *,
    realized_volatility: float | None = None,
    current_drawdown: float | None = None,
) -> RiskDecision:
    _validate_fraction("requested_weight", requested_weight)
    _validate_fraction("current_exposure", current_exposure)
    if realized_volatility is not None and (
        not _is_finite_real(realized_volatility)
        or not math.isfinite(realized_volatility)
        or realized_volatility < 0
    ):
        raise RiskEngineError("realized_volatility must be finite and non-negative.")
    if current_drawdown is not None and (
        not _is_finite_real(current_drawdown)
        or not math.isfinite(current_drawdown)
        or not 0 <= current_drawdown <= 1
    ):
        raise RiskEngineError("current_drawdown must be finite and in [0, 1].")

    if drawdown_breached(current_drawdown, limits):
        return RiskDecision(
            requested_weight=requested_weight,
            approved_weight=0.0,
            accepted=False,
            reasons=("REJECTED_MAX_DRAWDOWN_CIRCUIT_BREAKER",),
        )

    approved, reasons = calculate_approved_weight(
        requested_weight,
        current_exposure,
        realized_volatility,
        limits,
    )
    if not reasons and approved == requested_weight:
        reasons = ("APPROVED_WITHIN_LIMITS",)
    return RiskDecision(
        requested_weight=requested_weight,
        approved_weight=approved,
        accepted=approved > 0 or requested_weight == 0,
        reasons=reasons,
    )


def _validate_fraction(name: str, value: float) -> None:
    if not _is_finite_real(value) or not math.isfinite(value) or not 0 <= value <= 1:
        raise RiskEngineError(f"{name} must be finite and in [0, 1].")


def _is_finite_real(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)
