"""Deterministic screening of provider-supplied universe candidates."""

from datetime import datetime
import math
from numbers import Real

from data.market_data import normalize_ticker
from universe.filters import UniverseFilters
from universe.provider import UniverseDataProvider, UniverseProvider
from universe.types import (
    UniverseRejection,
    UniverseSelectionResult,
)


def select_universe(
    universe_provider: UniverseProvider,
    data_provider: UniverseDataProvider,
    as_of: datetime,
    filters: UniverseFilters | None = None,
) -> UniverseSelectionResult:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware.")
    criteria = filters or UniverseFilters()
    accepted: list[str] = []
    rejected: list[UniverseRejection] = []
    seen: set[str] = set()

    for raw_symbol in universe_provider.get_symbols():
        symbol = normalize_ticker(raw_symbol)
        if symbol in seen:
            continue
        seen.add(symbol)

        data = data_provider.fetch(symbol, as_of)
        if data is None or data.has_missing_data:
            rejected.append(UniverseRejection(symbol, "MISSING_DATA"))
            continue
        if data.as_of > as_of:
            rejected.append(UniverseRejection(symbol, "DATA_AFTER_AS_OF"))
            continue
        if data.current_price is None or not _finite_positive(data.current_price):
            rejected.append(UniverseRejection(symbol, "INVALID_OR_MISSING_PRICE"))
            continue
        if data.current_price < criteria.minimum_price:
            rejected.append(UniverseRejection(symbol, "PRICE_BELOW_MINIMUM"))
            continue
        if (
            data.history_count is None
            or isinstance(data.history_count, bool)
            or not isinstance(data.history_count, int)
            or data.history_count < criteria.minimum_history
        ):
            rejected.append(UniverseRejection(symbol, "INSUFFICIENT_HISTORY"))
            continue
        if data.market_cap is not None and not _finite_nonnegative(data.market_cap):
            rejected.append(UniverseRejection(symbol, "INVALID_MARKET_CAP"))
            continue
        if (
            criteria.minimum_market_cap is not None
            and data.market_cap is not None
            and data.market_cap < criteria.minimum_market_cap
        ):
            rejected.append(UniverseRejection(symbol, "MARKET_CAP_BELOW_MINIMUM"))
            continue
        accepted.append(symbol)

    return UniverseSelectionResult(tuple(accepted), tuple(rejected))


def _finite_nonnegative(value: float) -> bool:
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _finite_positive(value: float) -> bool:
    return _finite_nonnegative(value) and value > 0
