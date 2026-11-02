"""Typed target-position values returned by strategies."""

from dataclasses import dataclass
from datetime import datetime
import math


@dataclass(frozen=True)
class TargetPosition:
    symbol: str
    timestamp: datetime
    weight: float
    reason: str

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        if not math.isfinite(self.weight) or not -1.0 <= self.weight <= 1.0:
            raise ValueError("weight must be between -1 and 1")
        if not self.reason.strip():
            raise ValueError("reason cannot be empty")
