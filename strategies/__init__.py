"""Strategy contracts and deterministic research strategies."""

from strategies.base import Strategy
from strategies.momentum_regime import (
    DEFAULT_ALLOWED_REGIMES,
    MomentumRegimeInput,
    MomentumRegimeStrategy,
)
from strategies.moving_average import MovingAverageStrategy
from strategies.registry import StrategyRegistry, StrategyRegistryError
from strategies.types import TargetPosition

__all__ = [
    "DEFAULT_ALLOWED_REGIMES",
    "MomentumRegimeInput",
    "MomentumRegimeStrategy",
    "MovingAverageStrategy",
    "Strategy",
    "StrategyRegistry",
    "StrategyRegistryError",
    "TargetPosition",
]
