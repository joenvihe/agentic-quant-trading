from datetime import datetime, timedelta, timezone
import json

import pytest

from scripts.run_strategy_research import main


START = datetime(2024, 1, 1, tzinfo=timezone.utc)


class FakeMarketDataProvider:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.requested: list[str] = []

    def fetch(self, ticker: str) -> list[dict[str, object]]:
        self.requested.append(ticker)
        if self.error is not None:
            raise self.error
        offset = 0.0 if ticker == "SPY" else 20.0
        return [
            {
                "timestamp": START + timedelta(days=index),
                "open": 100.0 + offset + index * 0.2,
                "high": 100.5 + offset + index * 0.2,
                "low": 99.5 + offset + index * 0.2,
                "close": 100.0 + offset + index * 0.2,
                "volume": 1000.0 + index,
            }
            for index in range(300)
        ]


def test_pipeline_runs_with_fake_provider_and_writes_report_and_experiment(
    tmp_path, capsys
) -> None:
    provider = FakeMarketDataProvider()
    result = main(
        [
            "SPY",
            "QQQ",
            "--start-date",
            "2024-01-01",
            "--end-date",
            "2024-10-26",
            "--strategy",
            "moving_average",
            "--strategy-param",
            "fast_window=20",
            "--strategy-param",
            "slow_window=50",
            "--initial-cash",
            "10000",
            "--commission-bps",
            "2",
            "--slippage-bps",
            "3",
            "--output-dir",
            str(tmp_path / "reports"),
        ],
        provider=provider,
    )

    output = capsys.readouterr()
    assert result == 0
    assert provider.requested == ["SPY", "QQQ"]
    assert "Strategy: moving_average" in output.out
    assert "Experiment:" in output.out
    assert output.err == ""

    report_files = tuple((tmp_path / "reports").glob("moving_average-*.json"))
    assert len(report_files) == 1
    payload = json.loads(report_files[0].read_text(encoding="utf-8"))
    assert payload["strategy"]["symbols"] == ["SPY", "QQQ"]
    assert payload["strategy"]["parameters"] == {
        "fast_window": 20,
        "slow_window": 50,
    }
    assert payload["configuration"]["initial_cash"] == 10_000
    assert payload["configuration"]["commission_bps"] == 2
    assert payload["configuration"]["slippage_bps"] == 3
    assert payload["period"]["start"].startswith("2024-01-01")
    assert payload["period"]["end"].startswith("2024-10-26")
    assert len(tuple((tmp_path / "reports").glob("moving_average-*.csv"))) == 1
    assert len(tuple((tmp_path / "reports").glob("moving_average-*.html"))) == 1
    experiment_files = tuple((tmp_path / "reports" / "experiments").glob("*.json"))
    assert len(experiment_files) == 1
    experiment = json.loads(experiment_files[0].read_text(encoding="utf-8"))
    assert experiment["strategy_name"] == "moving_average"
    assert experiment["symbols"] == ["SPY", "QQQ"]
    assert set(experiment["output_files"]) == {
        str(path) for path in (tmp_path / "reports").glob("moving_average-*")
        if path.suffix in {".json", ".csv", ".html"}
    }


def test_momentum_regime_strategy_runs_without_converting_to_orders(
    tmp_path, capsys
) -> None:
    provider = FakeMarketDataProvider()

    exit_code = main(
        [
            "SPY",
            "--strategy",
            "momentum_regime",
            "--strategy-param",
            "allowed_regimes=BULL_STRONG,BULL_VOLATILE",
            "--output-dir",
            str(tmp_path / "reports"),
        ],
        provider=provider,
    )

    output = capsys.readouterr()
    assert exit_code == 0
    report = json.loads(
        next((tmp_path / "reports").glob("momentum_regime-*.json")).read_text(
            encoding="utf-8"
        )
    )
    assert report["strategy"]["parameters"] == {
        "allowed_regimes": ["BULL_STRONG", "BULL_VOLATILE"]
    }
    assert report["metrics"]["number_of_trades"] >= 0
    assert "Traceback" not in output.err


def test_date_range_uses_prior_history_to_warm_up_features(tmp_path, capsys) -> None:
    exit_code = main(
        [
            "SPY",
            "--start-date",
            "2024-06-01",
            "--end-date",
            "2024-10-26",
            "--output-dir",
            str(tmp_path / "reports"),
        ],
        provider=FakeMarketDataProvider(),
    )

    assert exit_code == 0
    assert capsys.readouterr().err == ""
    report = json.loads(
        next((tmp_path / "reports").glob("moving_average-*.json")).read_text(
            encoding="utf-8"
        )
    )
    assert report["period"]["start"].startswith("2024-06-01")
    assert report["trades"][0]["timestamp"].startswith("2024-06-02")


def test_provider_failure_has_clear_message_without_traceback_by_default(
    tmp_path, capsys
) -> None:
    exit_code = main(
        ["SPY", "--output-dir", str(tmp_path / "reports")],
        provider=FakeMarketDataProvider(RuntimeError("fake provider failure")),
    )

    output = capsys.readouterr()
    assert exit_code == 1
    assert "Unable to load validated market data for SPY" in output.err
    assert "fake provider failure" in output.err
    assert "Traceback" not in output.err


def test_debug_mode_shows_traceback_for_provider_failure(tmp_path, capsys) -> None:
    exit_code = main(
        [
            "SPY",
            "--debug",
            "--output-dir",
            str(tmp_path / "reports"),
        ],
        provider=FakeMarketDataProvider(RuntimeError("fake provider failure")),
    )
    output = capsys.readouterr()
    assert exit_code == 1
    assert "Traceback" in output.err


def test_invalid_strategy_symbol_or_dates_return_argument_exit_code(
    tmp_path, capsys
) -> None:
    provider = FakeMarketDataProvider()
    with pytest.raises(SystemExit) as invalid_strategy:
        main(
            ["SPY", "--strategy", "unknown", "--output-dir", str(tmp_path)],
            provider=provider,
        )
    assert invalid_strategy.value.code == 2

    with pytest.raises(SystemExit) as invalid_dates:
        main(
            [
                "SPY",
                "--start-date",
                "2024-10-01",
                "--end-date",
                "2024-01-01",
                "--output-dir",
                str(tmp_path),
            ],
            provider=provider,
        )
    assert invalid_dates.value.code == 2

    with pytest.raises(SystemExit) as invalid_costs:
        main(
            ["SPY", "--slippage-bps", "10000", "--output-dir", str(tmp_path)],
            provider=provider,
        )
    assert invalid_costs.value.code == 2
    assert provider.requested == []
