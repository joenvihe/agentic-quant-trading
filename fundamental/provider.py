"""Provider boundary for point-in-time fundamental snapshots."""

from datetime import datetime
from typing import Protocol

from fundamental.types import FundamentalSnapshot


class FundamentalDataError(ValueError):
    """Raised when a provider returns data outside its requested time boundary."""


class FundamentalDataProvider(Protocol):
    def fetch(
        self,
        symbol: str,
        as_of: datetime,
    ) -> FundamentalSnapshot | None:
        """Return only data published and available by the timezone-aware cutoff."""


def fetch_fundamental_snapshot(
    provider: FundamentalDataProvider,
    symbol: str,
    as_of: datetime,
) -> FundamentalSnapshot | None:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise FundamentalDataError("as_of must be timezone-aware.")
    snapshot = provider.fetch(symbol, as_of)
    if snapshot is None:
        return None
    if snapshot.symbol != symbol:
        raise FundamentalDataError("Provider returned a snapshot for another symbol.")
    if snapshot.as_of > as_of:
        raise FundamentalDataError("Provider returned data newer than the as-of cutoff.")
    return snapshot
