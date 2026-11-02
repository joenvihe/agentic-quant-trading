from collections.abc import Sequence
from datetime import datetime, timezone

import pytest

from universe import (
    StaticUniverseProvider,
    UniverseAssetData,
    UniverseDataProvider,
    UniverseFilters,
    UniverseProvider,
    select_universe,
)

AS_OF = datetime(2025, 6, 30, tzinfo=timezone.utc)


class FakeUniverseProvider:
    def __init__(self, symbols: Sequence[str]) -> None:
        self.symbols = symbols

    def get_symbols(self) -> Sequence[str]:
        return self.symbols


class FakeUniverseDataProvider:
    def __init__(self, data: dict[str, UniverseAssetData | None]) -> None:
        self.data = data
        self.fetched: list[str] = []

    def fetch(self, symbol: str, as_of: datetime) -> UniverseAssetData | None:
        self.fetched.append(symbol)
        return self.data.get(symbol)


def test_static_universe_normalizes_symbols_and_removes_duplicates() -> None:
    provider: UniverseProvider = StaticUniverseProvider(
        (" spy ", "SPY", "qqq", "QQQ")
    )

    assert provider.get_symbols() == ("SPY", "QQQ")


def test_universe_filters_and_reports_rejection_reasons() -> None:
    universe_provider: UniverseProvider = FakeUniverseProvider(
        ("LOW", "SHORT", "MISSING", "CAP", "NO_CAP", "GOOD", " low ")
    )
    data_provider: UniverseDataProvider = FakeUniverseDataProvider(
        {
            "LOW": UniverseAssetData(AS_OF, 5.0, 250, 1_000),
            "SHORT": UniverseAssetData(AS_OF, 20.0, 50, 1_000),
            "MISSING": None,
            "CAP": UniverseAssetData(AS_OF, 20.0, 300, 50),
            "NO_CAP": UniverseAssetData(AS_OF, 20.0, 300, None),
            "GOOD": UniverseAssetData(AS_OF, 20.0, 300, 500),
        }
    )

    result = select_universe(
        universe_provider,
        data_provider,
        AS_OF,
        UniverseFilters(minimum_price=10, minimum_history=200, minimum_market_cap=100),
    )

    assert result.accepted_symbols == ("NO_CAP", "GOOD")
    assert {
        rejection.symbol: rejection.reason for rejection in result.rejected_symbols
    } == {
        "LOW": "PRICE_BELOW_MINIMUM",
        "SHORT": "INSUFFICIENT_HISTORY",
        "MISSING": "MISSING_DATA",
        "CAP": "MARKET_CAP_BELOW_MINIMUM",
    }
    assert data_provider.fetched.count("LOW") == 1


def test_universe_rejects_missing_values_and_includes_missing_data_flag() -> None:
    result = select_universe(
        FakeUniverseProvider(("A", "B", "C")),
        FakeUniverseDataProvider(
            {
                "A": UniverseAssetData(AS_OF, None, 100),
                "B": UniverseAssetData(AS_OF, 10.0, 100, has_missing_data=True),
                "C": UniverseAssetData(AS_OF, 0.0, 100),
            }
        ),
        AS_OF,
        UniverseFilters(),
    )

    assert result.accepted_symbols == ()
    assert {item.reason for item in result.rejected_symbols} == {
        "MISSING_DATA",
        "INVALID_OR_MISSING_PRICE",
    }


def test_universe_rejects_metadata_after_the_cutoff() -> None:
    later = datetime(2025, 7, 1, tzinfo=timezone.utc)
    result = select_universe(
        FakeUniverseProvider(("A",)),
        FakeUniverseDataProvider({"A": UniverseAssetData(later, 10.0, 100)}),
        AS_OF,
    )

    assert result.accepted_symbols == ()
    assert result.rejected_symbols[0].reason == "DATA_AFTER_AS_OF"


def test_universe_filter_configuration_is_validated() -> None:
    with pytest.raises(ValueError, match="minimum_history"):
        UniverseFilters(minimum_history=-1)
