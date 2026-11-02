"""Domain types for timestamped news items."""

from dataclasses import dataclass
from datetime import datetime


def _require_aware(timestamp: datetime, field: str) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware.")


@dataclass(frozen=True)
class NewsItem:
    symbol: str
    published_at: datetime
    title: str
    source: str
    text: str | None = None
    url: str | None = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty.")
        _require_aware(self.published_at, "published_at")
        if not self.title.strip():
            raise ValueError("title cannot be empty.")
        if self.text is not None and not isinstance(self.text, str):
            raise ValueError("text must be a string or None.")
        if not self.source.strip():
            raise ValueError("source cannot be empty.")
