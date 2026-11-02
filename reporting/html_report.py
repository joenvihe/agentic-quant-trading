"""Escaped standalone HTML report rendering; does not launch a browser."""

from dataclasses import fields
from html import escape
import json
from pathlib import Path
from typing import Any

from reporting.charts import render_line_chart_svg
from reporting.research_report import ResearchReport
from reporting.tables import equity_rows, metrics_table, trade_rows


def render_html_report(report: ResearchReport) -> str:
    rows = equity_rows(report.backtest_result)
    metrics_html = "".join(
        f"<tr><th>{escape(str(row['metric']))}</th>"
        f"<td>{escape(_format(row['value']))}</td></tr>"
        for row in metrics_table(report.metrics)
    )
    trades_html = "".join(
        "<tr>"
        + "".join(f"<td>{escape(_format(value))}</td>" for value in trade.values())
        + "</tr>"
        for trade in trade_rows(report.backtest_result)
    )
    if not trades_html:
        trades_html = '<tr><td colspan="7">No trades</td></tr>'

    benchmark = _benchmark_html(report)
    warnings_html = (
        "<ul>"
        + "".join(f"<li>{escape(warning)}</li>" for warning in report.warnings)
        + "</ul>"
        if report.warnings
        else "<p>None</p>"
    )
    equity_chart = render_line_chart_svg(
        [point.equity for point in report.backtest_result.equity_curve],
        title="Equity curve",
    )
    drawdown_chart = render_line_chart_svg(
        [row["drawdown"] for row in rows],
        title="Drawdown",
    )
    summary = {
        "strategy_name": report.strategy_name,
        "symbols": report.symbols,
        "configuration": report.configuration,
        "strategy_parameters": report.strategy_parameters,
        "start": report.start,
        "end": report.end,
        "output_files": report.output_files,
        "initial_cash": report.backtest_result.initial_cash,
        "final_equity": report.backtest_result.final_equity,
    }
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Research report - {escape(report.strategy_name)}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#222}}
table{{border-collapse:collapse;width:100%;margin-bottom:1.5rem}}
th,td{{border:1px solid #ccc;padding:.45rem;text-align:left}}
th{{background:#f1f3f5}} section{{margin:2rem 0}} svg{{max-width:100%;height:auto}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f7f7f7;padding:1rem}}
</style></head>
<body>
<h1>Research report</h1>
<section><h2>Strategy and configuration</h2>
<pre>{escape(json.dumps(summary, default=str, indent=2, sort_keys=True))}</pre></section>
<section><h2>Performance metrics</h2><table><tbody>{metrics_html}</tbody></table></section>
<section><h2>Benchmark comparison</h2>{benchmark}</section>
<section><h2>Equity curve</h2>{equity_chart}</section>
<section><h2>Drawdown</h2>{drawdown_chart}</section>
<section><h2>Trades</h2><table><thead><tr>
<th>Symbol</th><th>Timestamp</th><th>Side</th><th>Quantity</th>
<th>Price</th><th>Commission</th><th>Slippage</th>
</tr></thead><tbody>{trades_html}</tbody></table></section>
<section><h2>Warnings</h2>{warnings_html}</section>
</body></html>
"""


def write_html_report(report: ResearchReport, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html_report(report), encoding="utf-8")
    return path


def _benchmark_html(report: ResearchReport) -> str:
    comparison = report.benchmark_comparison
    if comparison is None:
        return "<p>No benchmark comparison available.</p>"
    body = "".join(
        "<tr>"
        f"<th>{escape(item.name)}</th>"
        f"<td>{escape(_format(getattr(comparison.strategy, item.name)))}</td>"
        f"<td>{escape(_format(getattr(comparison.benchmark, item.name)))}</td>"
        "</tr>"
        for item in fields(comparison.strategy)
    )
    difference = escape(_format(comparison.total_return_difference))
    return (
        "<table><thead><tr><th>Metric</th><th>Strategy</th><th>Benchmark</th>"
        "</tr></thead><tbody>"
        f"{body}</tbody></table>"
        f"<p>Total return difference (strategy - benchmark): {difference}</p>"
    )


def _format(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, default=str, sort_keys=True)
    return str(value)
