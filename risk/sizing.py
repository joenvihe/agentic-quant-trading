"""Risk position-sizing helpers."""

from risk.limits import apply_weight_and_exposure_limits
from risk.types import RiskLimits
from risk.volatility import volatility_target_weight


def calculate_approved_weight(
    requested_weight: float,
    current_exposure: float,
    realized_volatility: float | None,
    limits: RiskLimits,
) -> tuple[float, tuple[str, ...]]:
    approved, reasons = apply_weight_and_exposure_limits(
        requested_weight, current_exposure, limits
    )
    volatility_adjusted, volatility_reason = volatility_target_weight(
        approved, realized_volatility, limits.target_volatility
    )
    if volatility_reason is not None:
        reasons += (volatility_reason,)
    return volatility_adjusted, reasons
