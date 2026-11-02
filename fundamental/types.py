"""Typed point-in-time fundamental snapshots and derived metrics."""

from dataclasses import dataclass
from datetime import datetime
import math
from numbers import Real


@dataclass(frozen=True)
class FundamentalSnapshot:
    symbol: str
    as_of: datetime
    ebit: float | None = None
    enterprise_value: float | None = None
    net_working_capital: float | None = None
    net_fixed_assets: float | None = None
    market_cap: float | None = None
    net_income: float | None = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty.")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware.")
        for name in (
            "ebit",
            "enterprise_value",
            "net_working_capital",
            "net_fixed_assets",
            "market_cap",
            "net_income",
        ):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(value)
            ):
                raise ValueError(f"{name} must be finite when provided.")


@dataclass(frozen=True)
class FundamentalMetrics:
    symbol: str
    as_of: datetime
    return_on_capital: float | None
    earnings_yield: float | None
    price_to_earnings: float | None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty.")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware.")
        for name in ("return_on_capital", "earnings_yield", "price_to_earnings"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(value)
            ):
                raise ValueError(f"{name} must be finite when provided.")
