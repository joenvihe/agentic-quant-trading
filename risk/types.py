"""Validated risk configuration and decision results."""

from dataclasses import dataclass
import math
from numbers import Real


@dataclass(frozen=True)
class RiskLimits:
    max_position_weight: float = 0.20
    max_portfolio_exposure: float = 1.00
    max_drawdown: float | None = 0.20
    target_volatility: float | None = None

    def __post_init__(self) -> None:
        for name in ("max_position_weight", "max_portfolio_exposure"):
            value = getattr(self, name)
            if (
                not _is_finite_real(value)
                or not math.isfinite(value)
                or not 0 <= value <= 1
            ):
                raise ValueError(f"{name} must be finite and in [0, 1].")
        if self.max_drawdown is not None and (
            not _is_finite_real(self.max_drawdown)
            or not math.isfinite(self.max_drawdown)
            or not 0 < self.max_drawdown <= 1
        ):
            raise ValueError("max_drawdown must be finite and in (0, 1].")
        if self.target_volatility is not None and (
            not _is_finite_real(self.target_volatility)
            or not math.isfinite(self.target_volatility)
            or self.target_volatility <= 0
        ):
            raise ValueError("target_volatility must be finite and positive.")


@dataclass(frozen=True)
class RiskDecision:
    requested_weight: float
    approved_weight: float
    accepted: bool
    reasons: tuple[str, ...]


def _is_finite_real(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)
