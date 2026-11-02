"""Interfaces for deterministic signal generators."""

from typing import Protocol

from features.engine import FeatureSeries
from signals.types import Signal


class SignalGenerator(Protocol):
    def generate(self, features: FeatureSeries) -> Signal:
        """Create a signal from already-calculated features."""
