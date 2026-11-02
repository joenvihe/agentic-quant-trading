"""Typed strategy interface."""

from typing import Protocol, TypeVar

from strategies.types import TargetPosition


InputT = TypeVar("InputT", contravariant=True)


class Strategy(Protocol[InputT]):
    @property
    def name(self) -> str:
        """Stable, explicit registry key."""

    def evaluate(self, inputs: InputT) -> TargetPosition:
        """Convert quantitative inputs into a target position."""
