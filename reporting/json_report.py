"""Stable JSON rendering and explicit-path report writing."""

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

from reporting.research_report import ResearchReport
from reporting.tables import equity_rows, trade_rows


def report_payload(report: ResearchReport) -> dict[str, Any]:
    return {
        "strategy": {
            "name": report.strategy_name,
            "parameters": report.strategy_parameters,
            "symbols": report.symbols,
        },
        "configuration": report.configuration,
        "period": {
            "start": report.start.isoformat() if report.start else None,
            "end": report.end.isoformat() if report.end else None,
        },
        "initial_cash": report.backtest_result.initial_cash,
        "final_equity": report.backtest_result.final_equity,
        "metrics": report.metrics,
        "benchmark_comparison": report.benchmark_comparison,
        "equity_curve": equity_rows(report.backtest_result),
        "trades": trade_rows(report.backtest_result),
        "warnings": report.warnings,
        "output_files": report.output_files,
    }


def render_json_report(report: ResearchReport, *, indent: int = 2) -> str:
    return json.dumps(
        report_payload(report),
        default=_json_default,
        allow_nan=False,
        indent=indent,
        sort_keys=True,
    )


def write_json_report(report: ResearchReport, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_json_report(report) + "\n", encoding="utf-8")
    return path


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "value") and isinstance(value.value, (str, int, float)):
        return value.value
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable.")
