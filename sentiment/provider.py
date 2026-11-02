"""News provider contracts and deterministic offline provider."""

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

from sentiment.types import NewsItem


class NewsProvider(Protocol):
    def fetch(
        self, symbol: str, start: datetime, end: datetime
    ) -> tuple[NewsItem, ...]:
        """Return news published in the inclusive UTC-aware time range."""


class FakeNewsProvider:
    """In-memory provider for tests and explicitly supplied research fixtures."""

    def __init__(self, items: Iterable[NewsItem]) -> None:
        self._items = tuple(items)

    def fetch(
        self, symbol: str, start: datetime, end: datetime
    ) -> tuple[NewsItem, ...]:
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("start must be timezone-aware.")
        if end.tzinfo is None or end.utcoffset() is None or start > end:
            raise ValueError("News query range is invalid.")
        normalized_symbol = symbol.strip().upper()
        return tuple(
            item
            for item in self._items
            if item.symbol.strip().upper() == normalized_symbol
            and start <= item.published_at <= end
        )
