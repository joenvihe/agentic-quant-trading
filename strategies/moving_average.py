"""Strategy that maps a moving-average signal to a long/flat target."""

from dataclasses import dataclass

from signals.types import Signal, SignalDirection
from strategies.types import TargetPosition


@dataclass(frozen=True)
class MovingAverageStrategy:
    name: str = "moving_average"

    def evaluate(self, signal: Signal) -> TargetPosition:
        if not isinstance(signal, Signal):
            raise TypeError("MovingAverageStrategy requires a Signal.")
        is_long = signal.direction is SignalDirection.LONG
        return TargetPosition(
            symbol=signal.symbol,
            timestamp=signal.timestamp,
            weight=1.0 if is_long else 0.0,
            reason=(
                f"LONG: {signal.source}"
                if is_long
                else f"FLAT: {signal.source}"
            ),
        )
