"""Typed, validated signal values."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import math
from typing import Any, Mapping


class SignalDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


@dataclass(frozen=True)
class Signal:
    symbol: str
    timestamp: datetime
    direction: SignalDirection
    strength: float
    source: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        if not isinstance(self.direction, SignalDirection):
            raise ValueError("direction must be a SignalDirection")
        if not math.isfinite(self.strength) or not 0.0 <= self.strength <= 1.0:
            raise ValueError("strength must be between 0 and 1")
        if not self.source.strip():
            raise ValueError("source cannot be empty")
