"""CSV serialization of report metrics, curves, trades, and warnings."""

import csv
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from io import StringIO
import json
from pathlib import Path
from typing import Any

from reporting.research_report import ResearchReport
from reporting.tables import equity_rows, metrics_table, trade_rows


def render_csv_report(report: ResearchReport) -> str:
    output = StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=("section", "timestamp", "symbol", "field", "value", "details"),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerow(
        {
            "section": "summary",
            "field": "strategy_name",
            "value": report.strategy_name,
            "details": _json_value(
                {
                    "symbols": report.symbols,
                    "configuration": report.configuration,
                    "parameters": report.strategy_parameters,
                    "start": report.start,
                    "end": report.end,
                    "output_files": report.output_files,
                    "initial_cash": report.backtest_result.initial_cash,
                    "final_equity": report.backtest_result.final_equity,
                }
            ),
        }
    )
    for row in metrics_table(report.metrics):
        writer.writerow(
            {"section": "metric", "field": row["metric"], "value": row["value"]}
        )
    if report.benchmark_comparison is not None:
        writer.writerow(
            {
                "section": "benchmark_comparison",
                "field": "strategy",
                "details": _json_value(report.benchmark_comparison),
            }
        )
    for row in equity_rows(report.backtest_result):
        writer.writerow(
            {
                "section": "equity_curve",
                "timestamp": row["timestamp"],
                "value": row["equity"],
                "details": _json_value(
                    {
                        "cash": row["cash"],
                        "market_value": row["market_value"],
                        "drawdown": row["drawdown"],
                    }
                ),
            }
        )
    for row in trade_rows(report.backtest_result):
        writer.writerow(
            {
                "section": "trade",
                "timestamp": row["timestamp"],
                "symbol": row["symbol"],
                "field": row["side"],
                "value": row["quantity"],
                "details": _json_value(row),
            }
        )
    for warning in report.warnings:
        writer.writerow({"section": "warning", "value": warning})
    return output.getvalue()


def write_csv_report(report: ResearchReport, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_csv_report(report), encoding="utf-8", newline="")
    return path


def _json_value(value: Any) -> str:
    return json.dumps(value, default=_json_default, sort_keys=True, allow_nan=False)


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable.")
