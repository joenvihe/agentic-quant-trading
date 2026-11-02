"""Robustness summaries for walk-forward out-of-sample folds."""

from dataclasses import dataclass
import math
from statistics import fmean, pstdev
from typing import Sequence

from evaluation.walk_forward import WalkForwardResult


@dataclass(frozen=True)
class RobustnessReport:
    total_folds: int
    valid_folds: int
    mean_out_of_sample_return: float | None
    return_volatility: float | None
    positive_return_fraction: float | None
    warnings: tuple[str, ...]


def summarize_robustness(
    results: Sequence[WalkForwardResult],
) -> RobustnessReport:
    returns = [
        result.out_of_sample_metrics.total_return
        for result in results
        if result.out_of_sample_metrics is not None
        and result.out_of_sample_metrics.total_return is not None
        and math.isfinite(result.out_of_sample_metrics.total_return)
    ]
    warnings = tuple(
        warning for result in results for warning in result.warnings
    )
    if not returns:
        return RobustnessReport(
            total_folds=len(results),
            valid_folds=0,
            mean_out_of_sample_return=None,
            return_volatility=None,
            positive_return_fraction=None,
            warnings=warnings + ("No valid out-of-sample returns to summarize.",),
        )
    return RobustnessReport(
        total_folds=len(results),
        valid_folds=len(returns),
        mean_out_of_sample_return=fmean(returns),
        return_volatility=pstdev(returns) if len(returns) > 1 else None,
        positive_return_fraction=sum(value > 0 for value in returns) / len(returns),
        warnings=warnings,
    )
