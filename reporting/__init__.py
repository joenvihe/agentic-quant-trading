"""Structured research reporting in JSON, CSV, and standalone HTML."""

from reporting.csv_report import write_csv_report
from reporting.html_report import render_html_report, write_html_report
from reporting.json_report import render_json_report, write_json_report
from reporting.research_report import ResearchReport, build_research_report

__all__ = [
    "ResearchReport",
    "build_research_report",
    "render_html_report",
    "render_json_report",
    "write_csv_report",
    "write_html_report",
    "write_json_report",
]
