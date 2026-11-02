"""Performance metrics and benchmark comparison."""

from evaluation.benchmark import buy_and_hold_benchmark
from evaluation.compare import PerformanceComparison, compare_performance
from evaluation.metrics import calculate_metrics
from evaluation.robustness import RobustnessReport, summarize_robustness
from evaluation.splits import (
    TemporalSplitError,
    TimeWindow,
    generate_time_splits,
    slice_market_data,
)
from evaluation.types import PerformanceMetrics
from evaluation.walk_forward import WalkForwardResult, run_walk_forward

__all__ = [
    "PerformanceComparison",
    "PerformanceMetrics",
    "RobustnessReport",
    "TemporalSplitError",
    "TimeWindow",
    "WalkForwardResult",
    "buy_and_hold_benchmark",
    "calculate_metrics",
    "compare_performance",
    "generate_time_splits",
    "run_walk_forward",
    "slice_market_data",
    "summarize_robustness",
]
