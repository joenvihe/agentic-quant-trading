"""Typed inputs and results for universe filtering."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UniverseAssetData:
    as_of: datetime
    current_price: float | None
    history_count: int | None
    market_cap: float | None = None
    has_missing_data: bool = False

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware.")


@dataclass(frozen=True)
class UniverseRejection:
    symbol: str
    reason: str


@dataclass(frozen=True)
class UniverseSelectionResult:
    accepted_symbols: tuple[str, ...]
    rejected_symbols: tuple[UniverseRejection, ...]
