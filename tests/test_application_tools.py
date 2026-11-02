from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from application.tools.backtest import BacktestRequest, execute_backtest
from application.tools.comparison import ComparisonRequest, compare_strategies
from application.tools.portfolio import PortfolioRequest, optimize_portfolio
from application.tools.reporting import ReportingRequest, generate_report
from application.tools.research import ResearchRequest, research_symbol
from application.tools.risk import RiskRequest, evaluate_risk_request
from application.tools.types import ToolResponse, to_serializable
from backtest.types import BacktestConfig, BacktestResult, EquityPoint
from config.settings import Settings
from data.market_data import MarketBar, MarketData
from evaluation.metrics import calculate_metrics
from risk.types import RiskLimits
from strategies.types import TargetPosition


START = datetime(2024, 1, 1, tzinfo=timezone.utc)


class FakeMarketDataProvider:
    def __init__(self) -> None:
        self.requested: list[str] = []

    def fetch(self, ticker: str) -> list[dict[str, object]]:
        self.requested.append(ticker)
        return [
            {
                "timestamp": START + timedelta(days=index),
                "open": 100.0 + index * 0.1,
                "high": 100.5 + index * 0.1,
                "low": 99.5 + index * 0.1,
                "close": 100.0 + index * 0.1,
                "volume": 1000.0 + index,
            }
            for index in range(260)
        ]


def _market_data() -> MarketData:
    bars = tuple(
        MarketBar(
            timestamp=START + timedelta(days=index),
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.0 + index,
            volume=1000.0,
        )
        for index in range(4)
    )
    return MarketData(ticker="SPY", bars=bars)


def _backtest(strategy_name: str, weight: float) -> BacktestResult:
    data = _market_data()
    positions = tuple(
        TargetPosition(
            symbol="SPY",
            timestamp=bar.timestamp,
            weight=weight if index == 0 else 0.0,
            reason="test",
        )
        for index, bar in enumerate(data.bars)
    )
    response = execute_backtest(
        BacktestRequest(data, positions, strategy_name, trace_id=f"bt-{strategy_name}")
    )
    assert response.success
    return BacktestResult(
        strategy_name=strategy_name,
        equity_curve=tuple(
            EquityPoint(
                timestamp=datetime.fromisoformat(point["timestamp"]),
                equity=point["equity"],
                cash=point["cash"],
                market_value=point["market_value"],
            )
            for point in response.data["equity_curve"]
        ),
        trades=(),
        initial_cash=response.data["initial_cash"],
        final_equity=response.data["final_equity"],
    )


def test_research_tool_uses_existing_service_and_returns_trace_and_warnings(
    tmp_path,
) -> None:
    provider = FakeMarketDataProvider()
    response = research_symbol(
        ResearchRequest("spy", trace_id="research-1"),
        provider,
        Settings(data_dir=tmp_path),
    )

    assert response.success
    assert response.trace_id == "research-1"
    assert response.data["ticker"] == "SPY"
    assert provider.requested == ["SPY"]
    json.dumps(response.data, allow_nan=False)


def test_research_tool_reports_validation_and_provider_errors(tmp_path) -> None:
    provider = FakeMarketDataProvider()
    invalid = research_symbol(
        ResearchRequest("../invalid"),
        provider,
        Settings(data_dir=tmp_path),
    )
    assert not invalid.success
    assert invalid.errors
    assert provider.requested == []


def test_backtest_tool_executes_domain_engine_and_validates_inputs() -> None:
    data = _market_data()
    positions = tuple(
        TargetPosition("SPY", bar.timestamp, 1.0, "test")
        for bar in data.bars
    )
    response = execute_backtest(
        BacktestRequest(data, positions, "buy_hold", BacktestConfig(1000), "backtest-1")
    )
    assert response.success
    assert response.trace_id == "backtest-1"
    assert len(response.data["equity_curve"]) == len(data.bars)

    invalid = execute_backtest(
        BacktestRequest(data, positions, "", trace_id="backtest-invalid")
    )
    assert not invalid.success
    assert invalid.errors


def test_comparison_tool_compares_aligned_strategy_results() -> None:
    response = compare_strategies(
        ComparisonRequest(
            (_backtest("flat", 0.0), _backtest("long", 1.0)),
            trace_id="compare-1",
        )
    )
    assert response.success
    assert response.data["baseline_strategy"] == "flat"
    assert "long" in response.data["comparisons_to_baseline"]
    json.dumps(response.data, allow_nan=False)


def test_comparison_tool_rejects_misaligned_or_duplicate_results() -> None:
    first = _backtest("first", 0.0)
    different_timestamps = BacktestResult(
        strategy_name="second",
        equity_curve=(
            EquityPoint(START + timedelta(days=1), 100.0, 100.0, 0.0),
        ),
        trades=(),
        initial_cash=100.0,
        final_equity=100.0,
    )
    response = compare_strategies(ComparisonRequest((first, different_timestamps)))
    assert not response.success
    assert "timestamps" in response.errors[0]
    duplicate = compare_strategies(
        ComparisonRequest((first, first))
    )
    assert not duplicate.success


def test_risk_tool_returns_decision_and_validation_errors() -> None:
    approved = evaluate_risk_request(
        RiskRequest(
            requested_weight=0.5,
            limits=RiskLimits(max_position_weight=0.25),
            trace_id="risk-1",
        )
    )
    assert approved.success
    assert approved.data["approved_weight"] == pytest.approx(0.25)
    assert approved.warnings

    rejected = evaluate_risk_request(RiskRequest(requested_weight=float("nan")))
    assert not rejected.success
    assert rejected.errors


def test_portfolio_tool_optimizes_existing_returns_and_reports_failures() -> None:
    request = PortfolioRequest(
        symbols=("A", "B"),
        returns_by_symbol={
            "A": (0.01, 0.02, -0.01, 0.015, 0.008),
            "B": (0.002, 0.001, 0.003, -0.001, 0.002),
        },
        trace_id="portfolio-1",
    )
    response = optimize_portfolio(request)
    assert response.success
    assert sum(response.data["weights"].values()) == pytest.approx(1.0)
    json.dumps(response.data, allow_nan=False)

    failed = optimize_portfolio(
        PortfolioRequest(
            symbols=("A", "A"),
            returns_by_symbol={"A": (0.1, 0.2)},
        )
    )
    assert not failed.success
    assert failed.errors


def test_reporting_tool_writes_requested_formats_under_safe_root(tmp_path) -> None:
    result = _backtest("moving_average", 1.0)
    response = generate_report(
        ReportingRequest(
            backtest_result=result,
            metrics=calculate_metrics(result),
            symbols=("SPY",),
            warnings=("synthetic test",),
            trace_id="report-1",
        ),
        output_root=tmp_path,
    )
    assert response.success
    assert set(response.data["files"]) == {"json", "csv", "html"}
    for report_path in response.data["files"].values():
        assert Path(report_path).is_file()
    payload_path = next(tmp_path.glob("report-*.json"))
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["strategy"]["symbols"] == ["SPY"]


@pytest.mark.parametrize("subdirectory", ("..", "../outside", r"..\outside", "C:temp"))
def test_reporting_tool_rejects_unsafe_paths(tmp_path, subdirectory) -> None:
    result = _backtest("flat", 0.0)
    response = generate_report(
        ReportingRequest(
            backtest_result=result,
            metrics=calculate_metrics(result),
            formats=("json",),
            subdirectory=subdirectory,
        ),
        output_root=tmp_path,
    )
    assert not response.success
    assert response.errors
    assert not (tmp_path.parent / "outside").exists()


def test_tool_responses_and_serializer_reject_non_json_values() -> None:
    response = ToolResponse(True, "trace", {"value": 1})
    assert response.success
    invalid_trace = evaluate_risk_request(
        RiskRequest(requested_weight=0.1, trace_id="../unsafe")
    )
    assert not invalid_trace.success
    assert invalid_trace.trace_id != "../unsafe"
    assert invalid_trace.errors
    with pytest.raises(TypeError):
        to_serializable(lambda: None)
    with pytest.raises(ValueError):
        to_serializable(float("inf"))
