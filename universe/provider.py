"""Provider contracts for universe membership and market metadata."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from universe.types import UniverseAssetData


class UniverseProvider(Protocol):
    def get_symbols(self) -> Sequence[str]:
        """Return candidate symbols for universe selection."""


class UniverseDataProvider(Protocol):
    def fetch(
        self,
        symbol: str,
        as_of: datetime,
    ) -> UniverseAssetData | None:
        """Return market metadata available by the timezone-aware cutoff."""
