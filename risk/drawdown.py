"""Drawdown circuit-breaker evaluation."""

from risk.types import RiskLimits


def drawdown_breached(
    current_drawdown: float | None,
    limits: RiskLimits,
) -> bool:
    return (
        limits.max_drawdown is not None
        and current_drawdown is not None
        and current_drawdown >= limits.max_drawdown
    )
