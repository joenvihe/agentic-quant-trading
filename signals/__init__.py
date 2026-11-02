"""Signal generation contracts and implementations."""

from signals.base import SignalGenerator
from signals.trend import MovingAverageCrossSignal, SignalGenerationError
from signals.types import Signal, SignalDirection

__all__ = [
    "MovingAverageCrossSignal",
    "Signal",
    "SignalDirection",
    "SignalGenerationError",
    "SignalGenerator",
]
