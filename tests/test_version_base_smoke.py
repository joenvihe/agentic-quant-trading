import json
import math

from data.synthetic import SyntheticMarketDataProvider
from scripts.run_strategy_research import main


def test_synthetic_provider_returns_repeatable_data() -> None:
    provider = SyntheticMarketDataProvider()

    assert list(provider.fetch("SPY")) == list(provider.fetch("SPY"))


def test_offline_demo_runs_full_pipeline_and_publishes_all_outputs(
    tmp_path, monkeypatch, capsys
) -> None:
    workspace = tmp_path / "research_workspace"
    monkeypatch.setenv("AQT_RESEARCH_WORKSPACE", str(workspace))

    exit_code = main(
        [
            "SPY",
            "QQQ",
            "IWM",
            "--demo",
            "--start-date",
            "2023-01-01",
            "--end-date",
            "2024-10-26",
            "--strategy",
            "moving_average",
        ]
    )

    assert exit_code == 0
    assert "DEMO / SYNTHETIC DATA" in capsys.readouterr().out
    reports = tuple((workspace / "reports").glob("moving_average-*.json"))
    csv_reports = tuple((workspace / "reports").glob("moving_average-*.csv"))
    html_reports = tuple((workspace / "reports").glob("moving_average-*.html"))
    experiments = tuple((workspace / "experiments").glob("*.json"))
    assert len(reports) == len(csv_reports) == len(html_reports) == len(experiments) == 1

    payload = json.loads(reports[0].read_text(encoding="utf-8"))
    assert payload["strategy"]["symbols"] == ["SPY", "QQQ", "IWM"]
    assert payload["equity_curve"]
    assert payload["metrics"]
    assert any("DEMO / SYNTHETIC DATA" in warning for warning in payload["warnings"])
    assert payload["benchmark_comparison"] is not None
    assert isinstance(payload["trades"], list)
    _assert_finite(payload)

    experiment = json.loads(experiments[0].read_text(encoding="utf-8"))
    assert experiment["strategy_name"] == "moving_average"
    assert any(
        "DEMO / SYNTHETIC DATA" in warning for warning in experiment["warnings"]
    )
    assert set(experiment["output_files"]) == {
        str(reports[0]),
        str(csv_reports[0]),
        str(html_reports[0]),
    }
    assert (workspace / "data" / "market_data" / "SPY.csv").is_file()
    assert (workspace / "data" / "market_data" / "QQQ.csv").is_file()
    assert (workspace / "data" / "market_data" / "IWM.csv").is_file()
    assert "2023-01-01" <= payload["period"]["start"][:10]
    assert payload["period"]["end"][:10] <= "2024-10-26"
    assert "DEMO / SYNTHETIC DATA" in html_reports[0].read_text(encoding="utf-8")
    assert csv_reports[0].read_text(encoding="utf-8").startswith(
        "section,timestamp,symbol,field,value,details\n"
    )


def _assert_finite(value: object) -> None:
    if isinstance(value, dict):
        for nested in value.values():
            _assert_finite(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _assert_finite(nested)
    elif isinstance(value, float):
        assert math.isfinite(value)
