"""Deterministic evidence-only text rendering for agent reports."""

from collections.abc import Mapping, Sequence
from typing import Any


NO_FUTURE_PERFORMANCE_CLAIM = (
    "Los resultados son históricos y no implican rentabilidad futura."
)


def render_research_summary(
    symbols: Sequence[str],
    strategies: Mapping[str, Mapping[str, Any]],
    comparison: Mapping[str, Any] | None,
    report_files: Mapping[str, str],
) -> str:
    sections = [
        f"Investigación histórica: {', '.join(symbols)}.",
        "Resultados calculados por el pipeline cuantitativo existente:",
    ]
    for name, result in strategies.items():
        metrics = result["metrics"]
        sections.append(
            f"- {name}: retorno total {_percent(metrics.get('total_return'))}; "
            f"CAGR {_percent(metrics.get('cagr'))}; "
            f"drawdown máximo {_percent(metrics.get('maximum_drawdown'))}; "
            f"Sharpe {_number(metrics.get('sharpe'))}."
        )
    if comparison is not None:
        baseline = comparison["baseline_strategy"]
        sections.append(f"Comparación calculada contra la estrategia base {baseline}:")
        for name, values in comparison["comparisons_to_baseline"].items():
            difference = values["total_return_difference"]
            sections.append(
                f"- {name}: diferencia de retorno total vs. {baseline}: "
                f"{_percent(difference)}."
            )
    else:
        sections.append(
            "No se compararon estrategias: solo se solicitó una."
        )
    if report_files:
        sections.append(
            "Reportes generados: "
            + ", ".join(f"{kind}={path}" for kind, path in report_files.items())
            + "."
        )
    sections.append(NO_FUTURE_PERFORMANCE_CLAIM)
    return "\n".join(sections)


def _percent(value: Any) -> str:
    if value is None:
        return "no disponible"
    return f"{value:.2%}"


def _number(value: Any) -> str:
    if value is None:
        return "no disponible"
    return f"{value:.3f}"
