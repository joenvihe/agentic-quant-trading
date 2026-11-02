"""Allowlisted deterministic orchestration of quantitative research tools."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
import math
from pathlib import Path
from typing import Any, Protocol

from agents.research.policy import (
    ALLOWED_STRATEGIES,
    AgentPolicyError,
    authorize_plan,
)
from agents.research.prompts import render_research_summary
from agents.research.state import AgentToolCall, ResearchAgentState
from application.services.strategy_research import (
    StrategyResearchError,
    StrategyResearchResult,
    run_strategy_research,
)
from application.tools.comparison import ComparisonRequest, compare_strategies
from application.tools.reporting import ReportingRequest, generate_report
from application.tools.types import resolve_trace_id, to_serializable
from config.settings import Settings
from data.market_data import MarketDataError, MarketDataProvider, normalize_ticker
from evaluation.compare import PerformanceComparison
from evaluation.types import PerformanceMetrics
from reporting.research_report import ResearchReport
from strategies.momentum_regime import REGIME_STATES


_STRATEGY_PARAMETERS = {
    "moving_average": frozenset({"fast_window", "slow_window"}),
    "momentum_regime": frozenset({"allowed_regimes"}),
}
_METRIC_NAMES = (
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe",
    "maximum_drawdown",
    "win_rate",
    "profit_factor",
)


@dataclass(frozen=True)
class ResearchAgentRequest:
    symbols: tuple[str, ...]
    strategies: tuple[str, ...]
    data_directory: Path
    output_directory: Path
    strategy_parameters: Mapping[str, Mapping[str, Any]] = field(
        default_factory=dict
    )
    start_date: date | None = None
    end_date: date | None = None
    initial_cash: float = 100_000.0
    commission_bps: float = 0.0
    slippage_bps: float = 0.0
    dry_run: bool = False
    trace_id: str | None = None


class ResearchPlanner(Protocol):
    def plan(self, request: ResearchAgentRequest) -> Sequence[AgentToolCall]:
        """Return a plan that is subsequently checked against static policy."""


class DeterministicResearchPlanner:
    """Choose the fixed research workflow from a validated structured request."""

    def plan(self, request: ResearchAgentRequest) -> tuple[AgentToolCall, ...]:
        from agents.research.policy import expected_plan

        return expected_plan(request.strategies)


class ResearchAgent:
    def __init__(
        self,
        planner: ResearchPlanner | None = None,
        *,
        workspace_root: str | Path | None = None,
    ) -> None:
        self._planner = planner or DeterministicResearchPlanner()
        configured_root = (
            Settings.from_env().research_workspace
            if workspace_root is None
            else workspace_root
        )
        if not isinstance(configured_root, (str, Path)) or not str(configured_root).strip():
            raise ValueError("workspace_root must be an explicitly configured path.")
        self._workspace_root = Path(configured_root).resolve()
        if self._workspace_root == Path(self._workspace_root.anchor):
            raise ValueError("workspace_root cannot be a filesystem root.")

    def run(
        self,
        request: ResearchAgentRequest,
        provider: MarketDataProvider,
    ) -> ResearchAgentState:
        if not isinstance(request, ResearchAgentRequest):
            trace_id, _ = resolve_trace_id(None)
            return _fail(
                ResearchAgentState(
                    request="Invalid structured research request.",
                    symbols=[],
                    selected_strategy=None,
                    trace_id=trace_id,
                ),
                "request must be a ResearchAgentRequest.",
            )
        trace_id, trace_error = resolve_trace_id(request.trace_id)
        symbols = (
            list(request.symbols)
            if isinstance(request.symbols, tuple)
            and all(isinstance(symbol, str) for symbol in request.symbols)
            else []
        )
        strategies = (
            request.strategies
            if isinstance(request.strategies, tuple)
            and all(isinstance(strategy, str) for strategy in request.strategies)
            else ()
        )
        state = ResearchAgentState(
            request=_request_description(request),
            symbols=symbols,
            selected_strategy=strategies[0]
            if len(strategies) == 1
            else None,
            trace_id=trace_id,
            dry_run=request.dry_run if isinstance(request.dry_run, bool) else False,
        )
        if trace_error:
            return _fail(state, trace_error)

        validation_error = _validate_request(
            request, provider, self._workspace_root
        )
        if validation_error:
            return _fail(state, validation_error)
        resolved_paths = _resolve_request_paths(
            request, self._workspace_root
        )
        data_directory, output_directory = resolved_paths

        try:
            plan = authorize_plan(
                self._planner.plan(request),
                request.strategies,
            )
        except (AgentPolicyError, TypeError, ValueError) as exc:
            state.tool_calls.append(
                {
                    "tool": "planner",
                    "arguments": {},
                    "trace_id": trace_id,
                    "status": "blocked",
                    "error": str(exc),
                }
            )
            return _fail(state, str(exc))

        if request.dry_run:
            state.tool_calls.extend(
                _tool_call_record(call, trace_id, "planned") for call in plan
            )
            state.warnings.append(
                "Dry-run: no research tools were executed and no data was fetched."
            )
            state.final_report = (
                "Plan validado; no se ejecutaron herramientas por estar activo "
                "el modo dry-run."
            )
            state.success = True
            return state

        results: dict[str, StrategyResearchResult] = {}
        comparison_data: Mapping[str, Any] | None = None
        report_files: Mapping[str, str] = {}

        for call in plan:
            if call.name == "strategy_research":
                strategy_name = call.arguments["strategy_name"]
                try:
                    result = run_strategy_research(
                        request.symbols,
                        provider,
                        data_directory=data_directory,
                        output_directory=output_directory,
                        strategy_name=strategy_name,
                        strategy_parameters=request.strategy_parameters.get(
                            strategy_name, {}
                        ),
                        start_date=request.start_date,
                        end_date=request.end_date,
                        initial_cash=request.initial_cash,
                        commission_bps=request.commission_bps,
                        slippage_bps=request.slippage_bps,
                    )
                except (
                    MarketDataError,
                    StrategyResearchError,
                    OSError,
                    ValueError,
                    TypeError,
                ) as exc:
                    state.tool_calls.append(
                        _tool_call_record(call, trace_id, "failed", error=str(exc))
                    )
                    return _fail(state, str(exc))
                results[strategy_name] = result
                state.tool_calls.append(
                    _tool_call_record(call, trace_id, "succeeded")
                )
                _append_strategy_evidence(state, strategy_name, result)

            elif call.name == "comparison":
                response = compare_strategies(
                    ComparisonRequest(
                        results=tuple(
                            results[name].report.backtest_result
                            for name in request.strategies
                        ),
                        trace_id=trace_id,
                    )
                )
                state.tool_calls.append(
                    _tool_call_record(
                        call,
                        trace_id,
                        "succeeded" if response.success else "failed",
                        error="; ".join(response.errors) if response.errors else None,
                    )
                )
                if not response.success:
                    return _fail(state, "; ".join(response.errors))
                comparison_data = response.data
                state.evidence.append(
                    {
                        "source": "comparison",
                        "trace_id": response.trace_id,
                        "data": dict(response.data),
                    }
                )
                state.warnings.extend(response.warnings)

            elif call.name == "reporting":
                baseline_name = request.strategies[0]
                baseline = results[baseline_name]
                _warn_missing_metrics(state, results)
                if comparison_data is None:
                    state.warnings.append(
                        "Only one strategy was requested; strategy-to-strategy "
                        "comparison is unavailable."
                    )
                report_warnings = _all_warnings(state.warnings)
                response = generate_report(
                    ReportingRequest(
                        backtest_result=baseline.report.backtest_result,
                        metrics=baseline.metrics,
                        benchmark_comparison=baseline.comparison,
                        configuration=baseline.report.configuration,
                        strategy_parameters=baseline.report.strategy_parameters,
                        symbols=baseline.report.symbols,
                        warnings=report_warnings,
                        trace_id=trace_id,
                    ),
                    output_root=output_directory,
                )
                state.tool_calls.append(
                    _tool_call_record(
                        call,
                        trace_id,
                        "succeeded" if response.success else "failed",
                        error="; ".join(response.errors) if response.errors else None,
                    )
                )
                if not response.success:
                    return _fail(state, "; ".join(response.errors))
                report_files = response.data["files"]
                state.evidence.append(
                    {
                        "source": "reporting",
                        "trace_id": response.trace_id,
                        "files": dict(report_files),
                    }
                )
                state.warnings.extend(response.warnings)

            else:
                # The policy should make this unreachable; fail closed if it does not.
                return _fail(state, f"Tool is not permitted: {call.name!r}.")

        if not results:
            return _fail(state, "The authorized plan produced no strategy evidence.")

        state.final_report = render_research_summary(
            results[request.strategies[0]].report.symbols,
            {
                name: {"metrics": to_serializable(result.metrics)}
                for name, result in results.items()
            },
            comparison_data,
            report_files,
        )
        state.warnings = list(_all_warnings(state.warnings))
        state.success = True
        return state


def run_research_agent(
    request: ResearchAgentRequest,
    provider: MarketDataProvider,
    *,
    planner: ResearchPlanner | None = None,
    workspace_root: str | Path | None = None,
) -> ResearchAgentState:
    return ResearchAgent(planner, workspace_root=workspace_root).run(request, provider)


def _validate_request(
    request: ResearchAgentRequest,
    provider: MarketDataProvider,
    workspace_root: Path,
) -> str | None:
    if not isinstance(request, ResearchAgentRequest):
        return "request must be a ResearchAgentRequest."
    if not isinstance(request.symbols, tuple) or not request.symbols:
        return "symbols must be a non-empty tuple."
    try:
        normalized = tuple(normalize_ticker(symbol) for symbol in request.symbols)
    except (MarketDataError, AttributeError, TypeError) as exc:
        return str(exc)
    if len(set(normalized)) != len(normalized):
        return "symbols must be unique after normalization."
    if (
        not isinstance(request.strategies, tuple)
        or not request.strategies
        or any(
            not isinstance(strategy, str) or strategy not in ALLOWED_STRATEGIES
            for strategy in request.strategies
        )
    ):
        return "strategies must be selected from the permitted strategy allowlist."
    if len(set(request.strategies)) != len(request.strategies):
        return "strategies must not contain duplicates."
    if not isinstance(request.strategy_parameters, Mapping):
        return "strategy_parameters must be a mapping."
    if any(not isinstance(strategy, str) for strategy in request.strategy_parameters):
        return "strategy parameter keys must be strategy names."
    unknown_strategies = set(request.strategy_parameters) - set(request.strategies)
    if unknown_strategies:
        return (
            "Parameters were supplied for strategies not selected in the request: "
            + ", ".join(sorted(unknown_strategies))
            + "."
        )
    for strategy, parameters in request.strategy_parameters.items():
        if not isinstance(parameters, Mapping):
            return f"Parameters for {strategy} must be a mapping."
        if any(not isinstance(name, str) for name in parameters):
            return f"Parameter names for {strategy} must be strings."
        unknown = set(parameters) - _STRATEGY_PARAMETERS[strategy]
        if unknown:
            return (
                f"Unknown {strategy} parameter(s): "
                + ", ".join(sorted(unknown))
                + "."
            )
        if strategy == "moving_average" and any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in parameters.values()
        ):
            return "Moving-average windows must be integers."
        if strategy == "momentum_regime" and "allowed_regimes" in parameters:
            regimes = parameters["allowed_regimes"]
            if isinstance(regimes, str):
                regimes = tuple(
                    value.strip() for value in regimes.split(",") if value.strip()
                )
            if (
                not isinstance(regimes, (tuple, list, set, frozenset))
                or any(not isinstance(regime, str) for regime in regimes)
                or set(regimes) - REGIME_STATES
            ):
                return "allowed_regimes contains an unknown regime state."
    if request.start_date is not None and (
        not isinstance(request.start_date, date)
        or isinstance(request.start_date, datetime)
    ):
        return "start_date must be a date."
    if request.end_date is not None and (
        not isinstance(request.end_date, date)
        or isinstance(request.end_date, datetime)
    ):
        return "end_date must be a date."
    if (
        request.start_date is not None
        and request.end_date is not None
        and request.start_date > request.end_date
    ):
        return "start_date cannot be after end_date."
    for name in ("data_directory", "output_directory"):
        value = getattr(request, name)
        if (
            not isinstance(value, (str, Path))
            or not str(value).strip()
        ):
            return f"{name} must be an explicitly configured path."
        configured_path = Path(value)
        if (
            configured_path.is_absolute()
            or configured_path.drive
            or configured_path.root
            or ".." in configured_path.parts
        ):
            return f"{name} must be relative to workspace_root without parent traversal."
        try:
            resolved_path = (workspace_root / configured_path).resolve()
            if not resolved_path.is_relative_to(workspace_root):
                return f"{name} escapes workspace_root after resolving symlinks."
        except OSError as exc:
            return f"{name} cannot be resolved safely: {exc}"
    if not _finite_real(request.initial_cash) or request.initial_cash <= 0:
        return "initial_cash must be finite and positive."
    if not _finite_real(request.commission_bps) or request.commission_bps < 0:
        return "commission_bps must be finite and non-negative."
    if (
        not _finite_real(request.slippage_bps)
        or not 0 <= request.slippage_bps < 10_000
    ):
        return "slippage_bps must be finite and in [0, 10000)."
    if not isinstance(request.dry_run, bool):
        return "dry_run must be a boolean."
    if not callable(getattr(provider, "fetch", None)):
        return "provider must implement fetch(ticker)."
    return None


def _resolve_request_paths(
    request: ResearchAgentRequest,
    workspace_root: Path,
) -> tuple[Path, Path]:
    data_directory = (workspace_root / Path(request.data_directory)).resolve()
    output_directory = (workspace_root / Path(request.output_directory)).resolve()
    return (
        data_directory,
        output_directory,
    )


def _finite_real(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _request_description(request: ResearchAgentRequest) -> str:
    symbols = (
        ",".join(request.symbols)
        if isinstance(request.symbols, tuple)
        and all(isinstance(symbol, str) for symbol in request.symbols)
        else "invalid"
    )
    strategies = (
        ",".join(request.strategies)
        if isinstance(request.strategies, tuple)
        and all(isinstance(strategy, str) for strategy in request.strategies)
        else "invalid"
    )
    start = (
        request.start_date.isoformat()
        if isinstance(request.start_date, date)
        and not isinstance(request.start_date, datetime)
        else "invalid" if request.start_date is not None else "unspecified"
    )
    end = (
        request.end_date.isoformat()
        if isinstance(request.end_date, date)
        and not isinstance(request.end_date, datetime)
        else "invalid" if request.end_date is not None else "unspecified"
    )
    return (
        f"symbols={symbols}; "
        f"strategies={strategies}; "
        f"start={start}; end={end}"
    )


def _tool_call_record(
    call: AgentToolCall,
    trace_id: str,
    status: str,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "tool": call.name,
        "arguments": dict(call.arguments),
        "trace_id": trace_id,
        "status": status,
    }
    if error is not None:
        record["error"] = error
    return record


def _append_strategy_evidence(
    state: ResearchAgentState,
    strategy_name: str,
    result: StrategyResearchResult,
) -> None:
    metrics: PerformanceMetrics = result.metrics
    comparison: PerformanceComparison = result.comparison
    report: ResearchReport = result.report
    state.evidence.append(
        {
            "source": "strategy_research",
            "trace_id": state.trace_id,
            "strategy": strategy_name,
            "metrics": to_serializable(metrics),
            "benchmark_comparison": to_serializable(comparison),
            "risk_limits": report.configuration.get("risk_limits"),
            "portfolio_allocator": report.configuration.get("portfolio_allocator"),
            "experiment_id": result.experiment.get("experiment_id"),
            "report_files": [str(path) for path in result.output_files],
        }
    )
    state.warnings.extend(report.warnings)


def _warn_missing_metrics(
    state: ResearchAgentState,
    results: Mapping[str, StrategyResearchResult],
) -> None:
    for strategy_name, result in results.items():
        metrics = result.metrics
        for metric_name in _METRIC_NAMES:
            if getattr(metrics, metric_name) is None:
                state.warnings.append(
                    f"{strategy_name}: {metric_name} is unavailable from the "
                    "available historical evidence."
                )


def _all_warnings(warnings: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(warnings))


def _fail(state: ResearchAgentState, error: str) -> ResearchAgentState:
    state.errors.append(error)
    state.success = False
    return state
