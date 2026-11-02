"""Typed values for reproducible backtest runs."""

from dataclasses import dataclass
from datetime import datetime
import math


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 100_000.0
    commission_bps: float = 0.0
    slippage_bps: float = 0.0

    def __post_init__(self) -> None:
        if (
            isinstance(self.initial_cash, bool)
            or not math.isfinite(self.initial_cash)
            or self.initial_cash <= 0
        ):
            raise ValueError("initial_cash must be finite and positive.")
        if not math.isfinite(self.commission_bps) or self.commission_bps < 0:
            raise ValueError("commission_bps must be finite and non-negative.")
        if (
            not math.isfinite(self.slippage_bps)
            or not 0 <= self.slippage_bps < 10_000
        ):
            raise ValueError("slippage_bps must be finite and in [0, 10000).")


@dataclass(frozen=True)
class Trade:
    symbol: str
    timestamp: datetime
    side: str
    quantity: float
    price: float
    commission: float
    slippage: float


@dataclass(frozen=True)
class EquityPoint:
    timestamp: datetime
    equity: float
    cash: float
    market_value: float


@dataclass(frozen=True)
class BacktestResult:
    strategy_name: str
    equity_curve: tuple[EquityPoint, ...]
    trades: tuple[Trade, ...]
    initial_cash: float
    final_equity: float
