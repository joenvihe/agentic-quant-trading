from datetime import datetime, timezone
from pathlib import Path

import pytest

from data.engine import run_market_data_engine
from data.market_data import (
    MarketDataDownloadError,
    MarketDataValidationError,
    normalize_market_data,
)
from data.storage import load_market_data, save_market_data


def valid_rows() -> list[dict[str, object]]:
    return [
        {
            "timestamp": "2024-01-02",
            "open": 100.0,
            "high": 105.0,
            "low": 99.0,
            "close": 104.0,
            "adjusted_close": 103.5,
            "volume": 1_000_000,
        },
        {
            "timestamp": "2024-01-03",
            "open": 104.0,
            "high": 108.0,
            "low": 102.0,
            "close": 107.0,
            "adjusted_close": 106.5,
            "volume": 1_100_000,
        },
    ]


def test_normalizes_valid_rows_and_naive_timestamps_to_utc() -> None:
    market_data = normalize_market_data(" spy ", valid_rows())

    assert market_data.ticker == "SPY"
    assert len(market_data.bars) == 2
    assert market_data.bars[0].timestamp == datetime(
        2024, 1, 2, tzinfo=timezone.utc
    )
    assert [bar.timestamp for bar in market_data.bars] == sorted(
        bar.timestamp for bar in market_data.bars
    )
    assert market_data.bars[0].adjusted_close == 103.5


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (
            [valid_rows()[0], valid_rows()[0]],
            "duplicado",
        ),
        (
            list(reversed(valid_rows())),
            "desordenado",
        ),
        (
            [{key: value for key, value in valid_rows()[0].items() if key != "close"}],
            "faltan columnas",
        ),
        (
            [{**valid_rows()[0], "close": None}],
            "close",
        ),
        (
            [{**valid_rows()[0], "open": 0}],
            "mayor que cero",
        ),
        (
            [{**valid_rows()[0], "high": 98.0}],
            "high",
        ),
        (
            [{**valid_rows()[0], "high": 103.0}],
            "high",
        ),
        (
            [{**valid_rows()[0], "low": 101.0}],
            "low",
        ),
        (
            [{**valid_rows()[0], "volume": -1}],
            "negativo",
        ),
        (
            [{**valid_rows()[0], "timestamp": "not-a-date"}],
            "timestamp",
        ),
        (
            [{**valid_rows()[0], "adjusted_close": None}],
            "adjusted_close",
        ),
    ],
)
def test_rejects_invalid_market_data(
    rows: list[dict[str, object]], message: str
) -> None:
    with pytest.raises(MarketDataValidationError, match=message):
        normalize_market_data("SPY", rows)


def test_adjusted_close_is_optional_when_provider_does_not_supply_it() -> None:
    rows = [
        {key: value for key, value in row.items() if key != "adjusted_close"}
        for row in valid_rows()
    ]

    market_data = normalize_market_data("SPY", rows)

    assert all(bar.adjusted_close is None for bar in market_data.bars)


def test_rejects_missing_numeric_values() -> None:
    with pytest.raises(MarketDataValidationError, match="close"):
        normalize_market_data("SPY", [{**valid_rows()[0], "close": float("nan")}])


def test_rejects_missing_timestamps() -> None:
    with pytest.raises(MarketDataValidationError, match="timestamp"):
        normalize_market_data("SPY", [{**valid_rows()[0], "timestamp": None}])


def test_rejects_partial_adjusted_close_column() -> None:
    rows = valid_rows()
    rows[1].pop("adjusted_close")

    with pytest.raises(MarketDataValidationError, match="adjusted_close"):
        normalize_market_data("SPY", rows)


def test_rejects_ticker_that_could_escape_storage_directory() -> None:
    with pytest.raises(MarketDataValidationError, match="Ticker"):
        normalize_market_data("../SPY", valid_rows())


def test_storage_round_trip_revalidates_and_preserves_rows(tmp_path: Path) -> None:
    expected = normalize_market_data("SPY", valid_rows())
    path = save_market_data(expected, tmp_path)

    actual = load_market_data(path, "SPY")

    assert path == tmp_path / "SPY.csv"
    assert actual == expected


def test_storage_round_trip_without_adjusted_close(tmp_path: Path) -> None:
    rows = [
        {key: value for key, value in row.items() if key != "adjusted_close"}
        for row in valid_rows()
    ]
    expected = normalize_market_data("SPY", rows)
    path = save_market_data(expected, tmp_path)

    actual = load_market_data(path, "SPY")

    assert actual == expected


class FakeProvider:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.requested_ticker: str | None = None

    def fetch(self, ticker: str) -> list[dict[str, object]]:
        self.requested_ticker = ticker
        return self.rows


def test_engine_downloads_validates_persists_and_reloads(
    tmp_path: Path,
) -> None:
    provider = FakeProvider(valid_rows())

    result = run_market_data_engine("spy", provider, tmp_path)

    assert provider.requested_ticker == "SPY"
    assert result.path == tmp_path / "market_data" / "SPY.csv"
    assert result.path.is_file()
    assert len(result.market_data.bars) == 2
    assert result.market_data == normalize_market_data("SPY", valid_rows())


def test_engine_does_not_persist_invalid_data(tmp_path: Path) -> None:
    provider = FakeProvider([{**valid_rows()[0], "volume": -1}])

    with pytest.raises(MarketDataValidationError, match="negativo"):
        run_market_data_engine("SPY", provider, tmp_path)

    assert not (tmp_path / "market_data").exists()


def test_engine_rejects_empty_provider_response(tmp_path: Path) -> None:
    provider = FakeProvider([])

    with pytest.raises(MarketDataDownloadError, match="no devolvió"):
        run_market_data_engine("SPY", provider, tmp_path)

    assert not (tmp_path / "market_data").exists()


def test_cli_prints_summary_for_injected_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts import download_market_data

    provider = FakeProvider(valid_rows())
    monkeypatch.setenv("AQT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        download_market_data, "YahooFinanceProvider", lambda: provider
    )

    exit_code = download_market_data.main(["spy"])

    output = capsys.readouterr()
    assert exit_code == 0
    assert "Ticker: SPY" in output.out
    assert "Registros recuperados: 2" in output.out
    assert str(tmp_path / "market_data" / "SPY.csv") in output.out


def test_cli_reports_provider_failure_without_success_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts import download_market_data

    monkeypatch.setenv("AQT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        download_market_data, "YahooFinanceProvider", lambda: FakeProvider([])
    )

    exit_code = download_market_data.main(["SPY"])

    output = capsys.readouterr()
    assert exit_code == 1
    assert "no devolvió" in output.err
    assert "Registros recuperados" not in output.out
