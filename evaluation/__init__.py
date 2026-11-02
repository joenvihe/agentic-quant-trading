"""Performance metrics and benchmark comparison."""

from evaluation.benchmark import buy_and_hold_benchmark
from evaluation.compare import PerformanceComparison, compare_performance
from evaluation.metrics import calculate_metrics
from evaluation.types import PerformanceMetrics

__all__ = [
    "PerformanceComparison",
    "PerformanceMetrics",
    "buy_and_hold_benchmark",
    "calculate_metrics",
    "compare_performance",
]
