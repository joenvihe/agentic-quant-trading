"""Application tool for serializing existing research results to disk."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
import re
from uuid import uuid4

from application.tools.types import (
    ToolResponse,
    error_response,
    resolve_trace_id,
    success_response,
    to_serializable,
)
from backtest.types import BacktestResult
from evaluation.compare import PerformanceComparison
from evaluation.types import PerformanceMetrics
from reporting.csv_report import write_csv_report
from reporting.html_report import write_html_report
from reporting.json_report import write_json_report
from reporting.research_report import ResearchReport, build_research_report


_SAFE_SUBDIRECTORY = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_WRITERS = {
    "json": write_json_report,
    "csv": write_csv_report,
    "html": write_html_report,
}


@dataclass(frozen=True)
class ReportingRequest:
    backtest_result: BacktestResult
    metrics: PerformanceMetrics
    benchmark_comparison: PerformanceComparison | None = None
    configuration: Mapping[str, object] = field(default_factory=dict)
    strategy_parameters: Mapping[str, object] = field(default_factory=dict)
    symbols: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    formats: tuple[str, ...] = ("json", "csv", "html")
    subdirectory: str = ""
    trace_id: str | None = None


def generate_report(
    request: ReportingRequest,
    *,
    output_root: str | Path,
) -> ToolResponse:
    trace_id, trace_error = resolve_trace_id(request.trace_id)
    if trace_error:
        return error_response(trace_id, trace_error)
    if (
        not isinstance(request.formats, tuple)
        or not request.formats
        or any(not isinstance(item, str) or item not in _WRITERS for item in request.formats)
    ):
        return error_response(trace_id, "formats must contain json, csv, and/or html.")
    if len(set(request.formats)) != len(request.formats):
        return error_response(trace_id, "formats must not contain duplicates.")
    if not isinstance(request.subdirectory, str):
        return error_response(trace_id, "subdirectory must be a string.")
    if request.subdirectory and not _SAFE_SUBDIRECTORY.fullmatch(request.subdirectory):
        return error_response(
            trace_id,
            "subdirectory must be one safe path segment using letters, numbers, "
            "underscores, or hyphens.",
        )
    if (
        not isinstance(request.backtest_result, BacktestResult)
        or not isinstance(request.metrics, PerformanceMetrics)
        or (
            request.benchmark_comparison is not None
            and not isinstance(request.benchmark_comparison, PerformanceComparison)
        )
    ):
        return error_response(
            trace_id,
            "reporting requires valid backtest, metrics, and comparison results.",
        )
    if (
        not isinstance(request.configuration, Mapping)
        or not isinstance(request.strategy_parameters, Mapping)
        or not isinstance(request.symbols, tuple)
        or any(not isinstance(symbol, str) for symbol in request.symbols)
        or not isinstance(request.warnings, tuple)
        or any(not isinstance(warning, str) for warning in request.warnings)
    ):
        return error_response(
            trace_id,
            "configuration, parameters, symbols, and warnings have invalid types.",
        )
    if not isinstance(output_root, (str, Path)):
        return error_response(trace_id, "output_root must be a configured path.")

    files: dict[str, str] = {}
    try:
        root = Path(output_root).resolve()
        destination = root / request.subdirectory if request.subdirectory else root
        resolved_destination = destination.resolve()
        if not resolved_destination.is_relative_to(root):
            return error_response(trace_id, "output directory escapes its allowed root.")
        resolved_destination.mkdir(parents=True, exist_ok=True)

        report_id = uuid4().hex
        report_paths = {
            report_format: resolved_destination / f"report-{report_id}.{report_format}"
            for report_format in request.formats
        }
        for path in report_paths.values():
            if path.is_symlink() or path.exists():
                return error_response(trace_id, "Refusing to overwrite an existing report.")
            if not path.resolve().is_relative_to(root):
                return error_response(trace_id, "report path escapes its allowed root.")
        report: ResearchReport = build_research_report(
            request.backtest_result,
            request.metrics,
            request.benchmark_comparison,
            configuration=request.configuration,
            strategy_parameters=request.strategy_parameters,
            symbols=request.symbols,
            warnings=request.warnings,
            output_files=tuple(str(path) for path in report_paths.values()),
        )
        serialized_report = to_serializable(report)
        for report_format, path in report_paths.items():
            _WRITERS[report_format](report, path)
            files[report_format] = str(path)
    except (OSError, TypeError, ValueError) as exc:
        return error_response(trace_id, str(exc), data={"written_files": files})
    return success_response(
        trace_id,
        {
            "report": serialized_report,
            "files": files,
        },
        warnings=request.warnings,
    )
