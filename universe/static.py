"""Explicit, normalized static universe provider."""

from collections.abc import Sequence

from data.market_data import normalize_ticker


class StaticUniverseProvider:
    def __init__(self, symbols: Sequence[str]) -> None:
        normalized: list[str] = []
        seen: set[str] = set()
        for symbol in symbols:
            try:
                candidate = normalize_ticker(symbol)
            except (AttributeError, TypeError) as exc:
                raise ValueError("Universe symbols must be valid ticker strings.") from exc
            if candidate not in seen:
                seen.add(candidate)
                normalized.append(candidate)
        self._symbols = tuple(normalized)

    def get_symbols(self) -> tuple[str, ...]:
        return self._symbols
