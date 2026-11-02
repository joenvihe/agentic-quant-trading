"""Point-in-time fundamental data contracts and quantitative rankings."""

from fundamental.metrics import calculate_fundamental_metrics
from fundamental.magic_formula import calculate_magic_formula_metrics
from fundamental.provider import (
    FundamentalDataError,
    FundamentalDataProvider,
    fetch_fundamental_snapshot,
)
from fundamental.ranking import FundamentalRank, rank_fundamentals
from fundamental.types import FundamentalMetrics, FundamentalSnapshot

__all__ = [
    "FundamentalDataProvider",
    "FundamentalDataError",
    "FundamentalMetrics",
    "FundamentalRank",
    "FundamentalSnapshot",
    "calculate_fundamental_metrics",
    "calculate_magic_formula_metrics",
    "fetch_fundamental_snapshot",
    "rank_fundamentals",
]
