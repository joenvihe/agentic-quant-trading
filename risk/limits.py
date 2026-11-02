"""Exposure and drawdown limit enforcement."""

from risk.types import RiskLimits


def apply_weight_and_exposure_limits(
    requested_weight: float,
    current_exposure: float,
    limits: RiskLimits,
) -> tuple[float, tuple[str, ...]]:
    approved = min(requested_weight, limits.max_position_weight)
    reasons: list[str] = []
    if approved < requested_weight:
        reasons.append("REDUCED_BY_MAX_POSITION_WEIGHT")

    available_exposure = max(
        0.0, limits.max_portfolio_exposure - current_exposure
    )
    exposure_limited = min(approved, available_exposure)
    if exposure_limited < approved:
        reasons.append("REDUCED_BY_MAX_PORTFOLIO_EXPOSURE")
    return exposure_limited, tuple(reasons)
