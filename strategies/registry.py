"""Explicit registry for strategy instances."""

from typing import Any

from strategies.base import Strategy


class StrategyRegistryError(Exception):
    """Raised for invalid or duplicate strategy registrations."""


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, Strategy[Any]] = {}

    def register(self, strategy: Strategy[Any]) -> None:
        name = getattr(strategy, "name", None)
        if not isinstance(name, str) or not name.strip():
            raise StrategyRegistryError("Strategy name cannot be empty.")
        if not callable(getattr(strategy, "evaluate", None)):
            raise StrategyRegistryError(
                f"Strategy {name} must provide an evaluate method."
            )
        if name in self._strategies:
            raise StrategyRegistryError(f"Strategy already registered: {name}.")
        self._strategies[name] = strategy

    def get(self, name: str) -> Strategy[Any]:
        try:
            return self._strategies[name]
        except KeyError as exc:
            raise StrategyRegistryError(f"Strategy is not registered: {name}.") from exc

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._strategies)
