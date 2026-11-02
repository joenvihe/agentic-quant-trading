"""Portfolio weight constraints and input validation."""

from collections.abc import Sequence
from dataclasses import dataclass
import math
from numbers import Real


@dataclass(frozen=True)
class PortfolioConstraints:
    min_weight: float = 0.0
    max_weight: float = 1.0
    fully_invested: bool = True

    def __post_init__(self) -> None:
        for name in ("min_weight", "max_weight"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(value)
                or not 0 <= value <= 1
            ):
                raise ValueError(f"{name} must be finite and in [0, 1].")
        if self.min_weight > self.max_weight:
            raise ValueError("min_weight cannot exceed max_weight.")
        if not isinstance(self.fully_invested, bool):
            raise ValueError("fully_invested must be a boolean.")


def validate_symbols(symbols: Sequence[str]) -> tuple[str, ...]:
    validated = tuple(symbols)
    if not validated:
        raise ValueError("At least one symbol is required.")
    if any(not isinstance(symbol, str) or not symbol.strip() for symbol in validated):
        raise ValueError("Symbols must be non-empty strings.")
    if len(set(validated)) != len(validated):
        raise ValueError("Symbols must be unique.")
    return validated


def constraints_are_feasible(
    symbol_count: int,
    constraints: PortfolioConstraints,
) -> bool:
    if not constraints.fully_invested:
        return False
    return (
        symbol_count * constraints.min_weight <= 1.0
        and symbol_count * constraints.max_weight >= 1.0
    )
