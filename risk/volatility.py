"""Historical realized-volatility and volatility-targeting calculations."""

import math
from collections.abc import Sequence
from statistics import pstdev


def calculate_realized_volatility(
    prices: Sequence[float],
    periods_per_year: int = 252,
) -> float | None:
    """Estimate annualized volatility from close prices using log returns."""
    if (
        isinstance(periods_per_year, bool)
        or not isinstance(periods_per_year, int)
        or periods_per_year <= 0
    ):
        raise ValueError("periods_per_year must be a positive integer.")
    if any(not math.isfinite(price) or price <= 0 for price in prices):
        raise ValueError("Prices must be finite and positive.")
    if len(prices) < 3:
        return None
    returns = [
        math.log(current / previous)
        for previous, current in zip(prices, prices[1:])
    ]
    volatility = pstdev(returns) * math.sqrt(periods_per_year)
    return volatility if math.isfinite(volatility) else None


def volatility_target_weight(
    current_weight: float,
    realized_volatility: float | None,
    target_volatility: float | None,
) -> tuple[float, str | None]:
    if target_volatility is None:
        return current_weight, None
    if realized_volatility is None:
        return 0.0, "REJECTED_VOLATILITY_UNAVAILABLE"
    if not math.isfinite(realized_volatility) or realized_volatility <= 0:
        return 0.0, "REJECTED_INVALID_REALIZED_VOLATILITY"
    scale = min(1.0, target_volatility / realized_volatility)
    adjusted = current_weight * scale
    if adjusted < current_weight:
        return adjusted, "REDUCED_BY_VOLATILITY_TARGET"
    return adjusted, None
