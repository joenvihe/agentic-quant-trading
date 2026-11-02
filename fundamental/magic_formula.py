"""Magic Formula metrics, deliberately kept separate from order generation."""

from fundamental.metrics import calculate_fundamental_metrics
from fundamental.types import FundamentalMetrics, FundamentalSnapshot


def calculate_magic_formula_metrics(
    snapshot: FundamentalSnapshot,
) -> FundamentalMetrics:
    """Calculate ROC (EBIT/invested capital) and EY (EBIT/enterprise value)."""
    return calculate_fundamental_metrics(snapshot)
