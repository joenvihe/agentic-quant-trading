from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path

from agents.research.agent import (
    ResearchAgentRequest,
    run_research_agent,
)
from agents.research.policy import ALLOWED_TOOLS
from agents.research.state import AgentToolCall


START = datetime(2024, 1, 1, tzinfo=timezone.utc)


class FakeMarketDataProvider:
    def __init__(self) -> None:
        self.requested: list[str] = []

    def fetch(self, ticker: str) -> list[dict[str, object]]:
        self.requested.append(ticker)
        return [
            {
                "timestamp": START + timedelta(days=index),
                "open": 100.0,
                "high": 100.5,
                "low": 99.5,
                "close": 100.0,
                "volume": 1000.0,
            }
            for index in range(300)
        ]


class FakePlanner:
    def __init__(self, calls: tuple[AgentToolCall, ...]) -> None:
        self.calls = calls
        self.invocations = 0

    def plan(self, request: ResearchAgentRequest) -> tuple[AgentToolCall, ...]:
        self.invocations += 1
        return self.calls


def _request(tmp_path, *, strategies=("moving_average",), **kwargs):
    options = {
        "start_date": date(2024, 1, 1),
        "end_date": date(2024, 10, 26),
        "trace_id": "agent-run-1",
    }
    options.update(kwargs)
    return ResearchAgentRequest(
        symbols=("SPY",),
        strategies=strategies,
        data_directory=tmp_path / "data",
        output_directory=tmp_path / "reports",
        **options,
    )


def test_dry_run_selects_only_allowed_tools_and_does_not_fetch_data(tmp_path) -> None:
    provider = FakeMarketDataProvider()
    request = _request(tmp_path, dry_run=True)

    state = run_research_agent(request, provider)
    serialized = state.to_dict()

    assert state.success
    assert state.trace_id == "agent-run-1"
    assert provider.requested == []
    assert not (tmp_path / "data").exists()
    assert [call["tool"] for call in state.tool_calls] == [
        "strategy_research",
        "reporting",
    ]
    assert all(call["status"] == "planned" for call in state.tool_calls)
    assert set(call["tool"] for call in state.tool_calls) <= ALLOWED_TOOLS
    json.dumps(serialized, allow_nan=False)


def test_agent_executes_pipeline_compares_strategies_and_tracks_evidence(
    tmp_path,
) -> None:
    provider = FakeMarketDataProvider()
    state = run_research_agent(
        _request(tmp_path, strategies=("moving_average", "momentum_regime")),
        provider,
    )

    assert state.success
    assert provider.requested == ["SPY", "SPY"]
    assert [call["tool"] for call in state.tool_calls] == [
        "strategy_research",
        "strategy_research",
        "comparison",
        "reporting",
    ]
    assert all(call["trace_id"] == state.trace_id for call in state.tool_calls)
    assert {item["source"] for item in state.evidence} == {
        "strategy_research",
        "comparison",
        "reporting",
    }
    assert "rentabilidad futura" in state.final_report
    assert all(path.exists() for path in (tmp_path / "reports").rglob("*") if path.is_file())
    json.dumps(state.to_dict(), allow_nan=False)


def test_missing_metric_evidence_is_reported_as_warning(tmp_path) -> None:
    state = run_research_agent(
        _request(tmp_path),
        FakeMarketDataProvider(),
    )

    assert state.success
    assert any("sharpe is unavailable" in warning for warning in state.warnings)
    assert "Sharpe no disponible" in state.final_report
    report_file = next(
        evidence["files"]["json"]
        for evidence in state.evidence
        if evidence["source"] == "reporting"
    )
    report = json.loads(Path(report_file).read_text(encoding="utf-8"))
    assert any("sharpe is unavailable" in warning for warning in report["warnings"])


def test_unapproved_planner_tool_is_blocked_before_any_execution(tmp_path) -> None:
    provider = FakeMarketDataProvider()
    planner = FakePlanner((AgentToolCall("paper_broker", {}),))
    state = run_research_agent(
        _request(tmp_path),
        provider,
        planner=planner,
    )

    assert not state.success
    assert "not permitted" in state.errors[0]
    assert provider.requested == []
    assert state.tool_calls[0]["status"] == "blocked"
    assert not (tmp_path / "data").exists()


def test_planner_cannot_change_strategy_or_workflow(tmp_path) -> None:
    provider = FakeMarketDataProvider()
    planner = FakePlanner(
        (
            AgentToolCall("strategy_research", {"strategy_name": "unknown"}),
            AgentToolCall("reporting", {}),
        )
    )
    state = run_research_agent(
        _request(tmp_path),
        provider,
        planner=planner,
    )

    assert not state.success
    assert "does not match" in state.errors[0]
    assert provider.requested == []


def test_trace_id_and_strategy_parameters_are_validated(tmp_path) -> None:
    provider = FakeMarketDataProvider()
    unsafe_trace = run_research_agent(
        _request(tmp_path, trace_id="../outside"),
        provider,
    )
    assert not unsafe_trace.success
    assert unsafe_trace.trace_id != "../outside"
    assert provider.requested == []

    unknown_parameter = run_research_agent(
        _request(
            tmp_path,
            strategy_parameters={"moving_average": {"python": "arbitrary"}},
        ),
        provider,
    )
    assert not unknown_parameter.success
    assert "Unknown moving_average parameter" in unknown_parameter.errors[0]
    assert provider.requested == []


def test_untrusted_or_relative_output_paths_are_rejected(tmp_path) -> None:
    provider = FakeMarketDataProvider()
    request = _request(tmp_path)
    relative_output = run_research_agent(
        replace(request, output_directory=Path("reports")),
        provider,
    )
    assert not relative_output.success
    assert "absolute" in relative_output.errors[0]

    traversal_data = run_research_agent(
        replace(request, data_directory=tmp_path / ".." / "outside"),
        provider,
    )
    assert not traversal_data.success
    assert "parent traversal" in traversal_data.errors[0]
    assert provider.requested == []
