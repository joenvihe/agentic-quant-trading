import csv
from datetime import datetime, timedelta, timezone
import json

from backtest.types import BacktestResult, EquityPoint, Trade
from evaluation.compare import PerformanceComparison
from evaluation.types import PerformanceMetrics
from reporting import (
    build_research_report,
    render_html_report,
    render_json_report,
    write_csv_report,
    write_html_report,
    write_json_report,
)
from reporting.csv_report import render_csv_report


START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def metrics(trades: int = 0) -> PerformanceMetrics:
    return PerformanceMetrics(
        total_return=0.1,
        cagr=0.05,
        annualized_volatility=0.2,
        sharpe=0.5,
        sortino=0.7,
        maximum_drawdown=-0.08,
        calmar=0.625,
        win_rate=0.5 if trades else None,
        profit_factor=1.5 if trades else None,
        number_of_trades=trades,
    )


def backtest_result(with_trades: bool = False) -> BacktestResult:
    trades = (
        (
            Trade(
                symbol="<SPY>",
                timestamp=START + timedelta(days=1),
                side="BUY",
                quantity=2.0,
                price=101.0,
                commission=0.25,
                slippage=0.1,
            ),
        )
        if with_trades
        else ()
    )
    return BacktestResult(
        strategy_name="<Trend & Growth>",
        equity_curve=(
            EquityPoint(START, 1000.0, 1000.0, 0.0),
            EquityPoint(START + timedelta(days=1), 1100.0, 800.0, 300.0),
            EquityPoint(START + timedelta(days=2), 1080.0, 800.0, 280.0),
        ),
        trades=trades,
        initial_cash=1000.0,
        final_equity=1080.0,
    )


def make_report(with_trades: bool = False):
    strategy = backtest_result(with_trades)
    benchmark = BacktestResult(
        strategy_name="Buy and Hold",
        equity_curve=strategy.equity_curve,
        trades=(),
        initial_cash=1000.0,
        final_equity=1040.0,
    )
    comparison = PerformanceComparison(
        strategy=metrics(len(strategy.trades)),
        benchmark=metrics(),
        total_return_difference=0.04,
    )
    return build_research_report(
        strategy,
        metrics(len(strategy.trades)),
        comparison,
        configuration={"commission_bps": 2.5},
        strategy_parameters={"fast_window": 20, "slow_window": 50},
        symbols=("SPY",),
        warnings=("<provider warning>",) if with_trades else (),
    )


def test_json_report_contains_configuration_metrics_comparison_and_series() -> None:
    report = make_report()

    payload = json.loads(render_json_report(report))

    assert payload["strategy"]["name"] == "<Trend & Growth>"
    assert payload["configuration"]["commission_bps"] == 2.5
    assert payload["metrics"]["total_return"] == 0.1
    assert payload["benchmark_comparison"]["total_return_difference"] == 0.04
    assert payload["equity_curve"][1]["drawdown"] == 0
    assert payload["equity_curve"][2]["drawdown"] == 1080 / 1100 - 1
    assert payload["trades"] == []
    assert payload["warnings"] == []


def test_csv_report_handles_empty_and_populated_trade_sections(tmp_path) -> None:
    empty_csv = render_csv_report(make_report())
    assert not any(
        row["section"] == "trade"
        for row in csv.DictReader(empty_csv.splitlines())
    )
    assert "benchmark_comparison" in empty_csv
    output = write_csv_report(make_report(True), tmp_path / "report.csv")

    with output.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert any(row["section"] == "trade" and row["symbol"] == "<SPY>" for row in rows)
    assert any(row["section"] == "warning" for row in rows)
    assert any(row["section"] == "equity_curve" for row in rows)


def test_html_report_escapes_all_user_content_and_embeds_charts() -> None:
    html = render_html_report(make_report(True))

    assert "&lt;Trend &amp; Growth&gt;" in html
    assert "&lt;SPY&gt;" in html
    assert "&lt;provider warning&gt;" in html
    assert "<svg" in html
    assert "Drawdown" in html
    assert "Benchmark comparison" in html
    assert "<script>" not in html


def test_report_writers_use_explicit_paths(tmp_path) -> None:
    report = make_report()

    json_path = write_json_report(report, tmp_path / "nested" / "report.json")
    html_path = write_html_report(report, tmp_path / "report.html")

    assert json.loads(json_path.read_text(encoding="utf-8"))["strategy"]["name"]
    assert "<html" in html_path.read_text(encoding="utf-8")
