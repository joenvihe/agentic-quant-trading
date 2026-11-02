"""Immutable paper-account positions and marked account snapshots."""

from dataclasses import dataclass
import math
from numbers import Real
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: float
    average_price: float
    market_price: float

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("position symbol cannot be empty.")
        if (
            isinstance(self.quantity, bool)
            or not isinstance(self.quantity, Real)
            or not math.isfinite(self.quantity)
            or self.quantity <= 0
            or isinstance(self.average_price, bool)
            or not isinstance(self.average_price, Real)
            or not math.isfinite(self.average_price)
            or self.average_price <= 0
            or isinstance(self.market_price, bool)
            or not isinstance(self.market_price, Real)
            or not math.isfinite(self.market_price)
            or self.market_price <= 0
        ):
            raise ValueError(
                "Position quantity and prices must be finite and positive."
            )
        object.__setattr__(self, "symbol", self.symbol.strip().upper())

    @property
    def market_value(self) -> float:
        return self.quantity * self.market_price


@dataclass(frozen=True)
class AccountState:
    cash: float
    positions: Mapping[str, Position]
    equity: float

    def __post_init__(self) -> None:
        if (
            isinstance(self.cash, bool)
            or not isinstance(self.cash, Real)
            or not math.isfinite(self.cash)
            or self.cash < 0
        ):
            raise ValueError("cash must be finite and non-negative.")
        if (
            isinstance(self.equity, bool)
            or not isinstance(self.equity, Real)
            or not math.isfinite(self.equity)
            or self.equity < 0
        ):
            raise ValueError("equity must be finite and non-negative.")
        normalized = dict(self.positions)
        if any(symbol != position.symbol for symbol, position in normalized.items()):
            raise ValueError("Position mapping keys must match position symbols.")
        expected_equity = self.cash + math.fsum(
            position.market_value for position in normalized.values()
        )
        if not math.isclose(
            self.equity, expected_equity, rel_tol=1e-12, abs_tol=1e-9
        ):
            raise ValueError("equity must equal cash plus position market value.")
        object.__setattr__(self, "positions", MappingProxyType(normalized))
