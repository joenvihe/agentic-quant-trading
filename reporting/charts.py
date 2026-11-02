"""Dependency-free SVG chart generation for report embedding."""

from html import escape
import math
from collections.abc import Sequence


def render_line_chart_svg(
    values: Sequence[float | None],
    *,
    title: str,
    width: int = 720,
    height: int = 240,
) -> str:
    if width < 100 or height < 80:
        raise ValueError("Chart dimensions are too small.")
    valid = [value for value in values if value is not None and math.isfinite(value)]
    if not valid:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" role="img"><title>{escape(title)}</title>'
            '<text x="12" y="24">No data available</text></svg>'
        )

    left, right, top, bottom = 48.0, width - 16.0, 30.0, height - 24.0
    minimum, maximum = min(valid), max(valid)
    span = maximum - minimum or 1.0
    points = []
    count = max(1, len(values) - 1)
    for index, value in enumerate(values):
        if value is None or not math.isfinite(value):
            continue
        x = left + (right - left) * index / count
        y = bottom - (bottom - top) * (value - minimum) / span
        points.append(f"{x:.2f},{y:.2f}")
    polyline = " ".join(points)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" role="img">'
        f"<title>{escape(title)}</title>"
        f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" '
        'stroke="#777"/>'
        f'<polyline fill="none" stroke="#1769aa" stroke-width="2" '
        f'points="{polyline}"/></svg>'
    )
