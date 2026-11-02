"""Deterministic fundamental metric calculations with explicit missing values."""

import math
from numbers import Real

from fundamental.types import FundamentalMetrics, FundamentalSnapshot


def calculate_fundamental_metrics(
    snapshot: FundamentalSnapshot,
) -> FundamentalMetrics:
    invested_capital = _sum_if_present(
        snapshot.net_working_capital,
        snapshot.net_fixed_assets,
    )
    roc = _safe_positive_denominator_ratio(snapshot.ebit, invested_capital)
    earnings_yield = _safe_positive_denominator_ratio(
        snapshot.ebit,
        snapshot.enterprise_value,
    )
    price_to_earnings = _safe_positive_denominator_ratio(
        snapshot.market_cap,
        snapshot.net_income,
    )
    return FundamentalMetrics(
        symbol=snapshot.symbol,
        as_of=snapshot.as_of,
        return_on_capital=roc,
        earnings_yield=earnings_yield,
        price_to_earnings=price_to_earnings,
    )


def _sum_if_present(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    total = left + right
    return total if math.isfinite(total) else None


def _safe_positive_denominator_ratio(
    numerator: float | None,
    denominator: float | None,
) -> float | None:
    if (
        numerator is None
        or denominator is None
        or not _finite_real(numerator)
        or not _finite_real(denominator)
        or denominator <= 0
    ):
        return None
    ratio = numerator / denominator
    return ratio if math.isfinite(ratio) else None


def _finite_real(value: object) -> bool:
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )
