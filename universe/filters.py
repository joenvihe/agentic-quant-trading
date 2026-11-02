"""Validated criteria for deterministic universe selection."""

from dataclasses import dataclass
import math
from numbers import Real


@dataclass(frozen=True)
class UniverseFilters:
    minimum_price: float = 0.0
    minimum_history: int = 0
    minimum_market_cap: float | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.minimum_price, bool)
            or not isinstance(self.minimum_price, Real)
            or not math.isfinite(self.minimum_price)
            or self.minimum_price < 0
        ):
            raise ValueError("minimum_price must be finite and non-negative.")
        if (
            isinstance(self.minimum_history, bool)
            or not isinstance(self.minimum_history, int)
            or self.minimum_history < 0
        ):
            raise ValueError("minimum_history must be a non-negative integer.")
        if self.minimum_market_cap is not None and (
            isinstance(self.minimum_market_cap, bool)
            or not isinstance(self.minimum_market_cap, Real)
            or not math.isfinite(self.minimum_market_cap)
            or self.minimum_market_cap < 0
        ):
            raise ValueError("minimum_market_cap must be finite and non-negative.")
