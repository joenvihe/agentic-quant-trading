from datetime import datetime, timezone

import pytest

from fundamental import (
    FundamentalDataProvider,
    FundamentalDataError,
    FundamentalSnapshot,
    calculate_fundamental_metrics,
    calculate_magic_formula_metrics,
    fetch_fundamental_snapshot,
    rank_fundamentals,
)


AS_OF = datetime(2025, 6, 30, tzinfo=timezone.utc)


class FakeFundamentalProvider:
    def __init__(self, snapshot: FundamentalSnapshot | None) -> None:
        self.snapshot = snapshot
        self.requested: tuple[str, datetime] | None = None

    def fetch(self, symbol: str, as_of: datetime) -> FundamentalSnapshot | None:
        self.requested = (symbol, as_of)
        return self.snapshot


def test_fundamental_provider_and_magic_formula_metrics() -> None:
    snapshot = FundamentalSnapshot(
        symbol="AAA",
        as_of=AS_OF,
        ebit=100.0,
        enterprise_value=1000.0,
        net_working_capital=100.0,
        net_fixed_assets=100.0,
        market_cap=1200.0,
        net_income=60.0,
    )
    fake_provider = FakeFundamentalProvider(snapshot)
    provider: FundamentalDataProvider = fake_provider

    fetched = fetch_fundamental_snapshot(provider, "AAA", AS_OF)
    assert fetched == snapshot
    assert fake_provider.requested == ("AAA", AS_OF)
    assert calculate_magic_formula_metrics(snapshot).return_on_capital == pytest.approx(
        0.5
    )
    metrics = calculate_fundamental_metrics(snapshot)
    assert metrics.earnings_yield == pytest.approx(0.1)
    assert metrics.price_to_earnings == pytest.approx(20.0)


def test_fundamental_provider_enforces_as_of_cutoff() -> None:
    future = FundamentalSnapshot(
        "AAA", datetime(2025, 7, 1, tzinfo=timezone.utc), ebit=10.0
    )
    with pytest.raises(FundamentalDataError, match="newer"):
        fetch_fundamental_snapshot(FakeFundamentalProvider(future), "AAA", AS_OF)


def test_missing_fundamental_data_remains_none_instead_of_zero() -> None:
    snapshot = FundamentalSnapshot(symbol="BBB", as_of=AS_OF)

    metrics = calculate_fundamental_metrics(snapshot)

    assert metrics.return_on_capital is None
    assert metrics.earnings_yield is None
    assert metrics.price_to_earnings is None


def test_zero_denominators_are_unavailable() -> None:
    snapshot = FundamentalSnapshot(
        symbol="CCC",
        as_of=AS_OF,
        ebit=10.0,
        enterprise_value=0.0,
        net_working_capital=0.0,
        net_fixed_assets=0.0,
        market_cap=100.0,
        net_income=0.0,
    )

    metrics = calculate_fundamental_metrics(snapshot)

    assert metrics.return_on_capital is None
    assert metrics.earnings_yield is None
    assert metrics.price_to_earnings is None


def test_fundamental_ranking_is_combined_and_missing_metrics_are_not_zero() -> None:
    metrics = (
        calculate_fundamental_metrics(
            FundamentalSnapshot(
                "AAA", AS_OF, ebit=100, enterprise_value=1000,
                net_working_capital=100, net_fixed_assets=100,
            )
        ),
        calculate_fundamental_metrics(
            FundamentalSnapshot(
                "BBB", AS_OF, ebit=40, enterprise_value=1000,
                net_working_capital=100, net_fixed_assets=100,
            )
        ),
        calculate_fundamental_metrics(FundamentalSnapshot("CCC", AS_OF)),
    )

    ranks = rank_fundamentals(metrics, AS_OF)

    assert [item.symbol for item in ranks] == ["AAA", "BBB", "CCC"]
    assert ranks[0].combined_rank == 1
    assert ranks[-1].combined_rank is None


def test_fundamental_ranking_rejects_duplicates_and_data_after_cutoff() -> None:
    metric = calculate_fundamental_metrics(FundamentalSnapshot("AAA", AS_OF))
    with pytest.raises(ValueError, match="unique"):
        rank_fundamentals((metric, metric), AS_OF)
    later = calculate_fundamental_metrics(
        FundamentalSnapshot("BBB", datetime(2025, 7, 1, tzinfo=timezone.utc))
    )
    with pytest.raises(ValueError, match="newer"):
        rank_fundamentals((metric, later), AS_OF)
