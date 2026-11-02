from datetime import datetime, timedelta, timezone
import re

from scripts import research_asset


def valid_rows(count: int = 300) -> list[dict[str, object]]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(count):
        close = 100.0 + index * 0.2
        rows.append(
            {
                "timestamp": start + timedelta(days=index),
                "open": close,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "volume": 1000 + index,
            }
        )
    return rows


class FakeProvider:
    def __init__(
        self,
        rows: list[dict[str, object]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.rows = rows if rows is not None else valid_rows()
        self.error = error
        self.requested_tickers: list[str] = []

    def fetch(self, ticker: str) -> list[dict[str, object]]:
        self.requested_tickers.append(ticker)
        if self.error is not None:
            raise self.error
        return self.rows


def install_provider(monkeypatch, provider: FakeProvider) -> None:
    monkeypatch.setattr(
        research_asset,
        "YahooFinanceProvider",
        lambda: provider,
    )


def test_valid_ticker_runs_pipeline_and_renders_report(
    tmp_path, monkeypatch, capsys
) -> None:
    provider = FakeProvider()
    install_provider(monkeypatch, provider)
    monkeypatch.setenv("AQT_DATA_DIR", str(tmp_path))

    exit_code = research_asset.main(["spy"])

    output = capsys.readouterr()
    assert exit_code == 0
    assert provider.requested_tickers == ["SPY"]
    assert "QUANT RESEARCH REPORT" in output.out
    assert "Ticker: SPY" in output.out
    assert "Status: PASS" in output.out
    assert "Records: 300" in output.out
    assert "SMA20:" in output.out
    assert "Composite Momentum Score: N/A (requiere universo comparativo)" in output.out
    assert re.search(
        r"Regime: (BULL_STRONG|BULL_VOLATILE|RANGE|TRANSITION|BEAR|CHAOTIC)",
        output.out,
    )
    assert "Reason Codes:" in output.out
    assert output.err == ""


def test_report_is_deterministic_for_identical_market_data(
    tmp_path, monkeypatch, capsys
) -> None:
    provider = FakeProvider()
    install_provider(monkeypatch, provider)
    monkeypatch.setenv("AQT_DATA_DIR", str(tmp_path))

    first_exit_code = research_asset.main(["SPY"])
    first_output = capsys.readouterr()
    second_exit_code = research_asset.main(["SPY"])
    second_output = capsys.readouterr()

    assert first_exit_code == second_exit_code == 0
    assert first_output.out == second_output.out
    assert first_output.err == second_output.err == ""


def test_rejects_invalid_ticker_without_provider_call(
    monkeypatch, capsys
) -> None:
    provider = FakeProvider()
    install_provider(monkeypatch, provider)

    exit_code = research_asset.main(["../SPY"])

    output = capsys.readouterr()
    assert exit_code == 1
    assert "Status: FAIL" in output.err
    assert "Ticker no válido" in output.err
    assert provider.requested_tickers == []
    assert output.out == ""


def test_empty_market_history_is_reported_without_traceback(
    tmp_path, monkeypatch, capsys
) -> None:
    provider = FakeProvider(rows=[])
    install_provider(monkeypatch, provider)
    monkeypatch.setenv("AQT_DATA_DIR", str(tmp_path))

    exit_code = research_asset.main(["SPY"])

    output = capsys.readouterr()
    assert exit_code == 1
    assert "Status: FAIL" in output.err
    assert "no devolvió barras históricas" in output.err
    assert "Traceback" not in output.err
    assert output.out == ""


def test_insufficient_history_reports_na_and_warning(
    tmp_path, monkeypatch, capsys
) -> None:
    provider = FakeProvider(rows=valid_rows(3))
    install_provider(monkeypatch, provider)
    monkeypatch.setenv("AQT_DATA_DIR", str(tmp_path))

    exit_code = research_asset.main(["SPY"])

    output = capsys.readouterr()
    assert exit_code == 0
    assert "Status: WARNING" in output.out
    assert "Historial insuficiente" in output.out
    assert "SMA20: N/A" in output.out
    assert "1M: N/A" in output.out
    assert "Regime: TRANSITION" in output.out
    assert "Traceback" not in output.err


def test_provider_exception_is_reported_without_traceback(
    tmp_path, monkeypatch, capsys
) -> None:
    provider = FakeProvider(error=RuntimeError("network unavailable"))
    install_provider(monkeypatch, provider)
    monkeypatch.setenv("AQT_DATA_DIR", str(tmp_path))

    exit_code = research_asset.main(["SPY"])

    output = capsys.readouterr()
    assert exit_code == 1
    assert "Status: FAIL" in output.err
    assert "No se pudieron descargar datos de mercado para SPY" in output.err
    assert "network unavailable" in output.err
    assert "Traceback" not in output.err
    assert output.out == ""


def test_invalid_market_data_is_reported_as_data_quality_failure(
    tmp_path, monkeypatch, capsys
) -> None:
    rows = valid_rows(1)
    rows[0]["close"] = -1
    provider = FakeProvider(rows=rows)
    install_provider(monkeypatch, provider)
    monkeypatch.setenv("AQT_DATA_DIR", str(tmp_path))

    exit_code = research_asset.main(["SPY"])

    output = capsys.readouterr()
    assert exit_code == 1
    assert "Status: FAIL" in output.err
    assert "close" in output.err
    assert output.out == ""


def test_malformed_provider_row_is_reported_without_traceback(
    tmp_path, monkeypatch, capsys
) -> None:
    provider = FakeProvider(rows=[{"timestamp": "2025-01-01"}, 42])  # type: ignore[list-item]
    install_provider(monkeypatch, provider)
    monkeypatch.setenv("AQT_DATA_DIR", str(tmp_path))

    exit_code = research_asset.main(["SPY"])

    output = capsys.readouterr()
    assert exit_code == 1
    assert "Status: FAIL" in output.err
    assert "Fila 2" in output.err
    assert "Traceback" not in output.err
    assert output.out == ""
