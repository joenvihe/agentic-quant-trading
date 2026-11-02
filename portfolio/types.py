"""Typed portfolio allocation results."""

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class AllocationResult:
    weights: Mapping[str, float]
    expected_return: float | None
    expected_volatility: float | None
    expected_sharpe: float | None
    success: bool
    message: str
