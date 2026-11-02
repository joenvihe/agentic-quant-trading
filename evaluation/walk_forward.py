"""Train-only parameter selection and chronological out-of-sample evaluation."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, fields
import math
from typing import Any

from backtest.types import BacktestResult
from data.market_data import MarketData
from evaluation.metrics import calculate_metrics
from evaluation.splits import (
    SplitMode,
    TimeWindow,
    generate_time_splits,
    slice_market_data,
)
from evaluation.types import PerformanceMetrics


BacktestEvaluator = Callable[[MarketData, Mapping[str, Any]], BacktestResult]
_METRIC_NAMES = frozenset(field.name for field in fields(PerformanceMetrics))


@dataclass(frozen=True)
class WalkForwardResult:
    window: TimeWindow
    evaluated_parameters: tuple[Mapping[str, Any], ...]
    selected_parameters: Mapping[str, Any] | None
    metric_name: str
    maximize_metric: bool
    in_sample_metrics: PerformanceMetrics | None
    out_of_sample_metrics: PerformanceMetrics | None
    warnings: tuple[str, ...]


def run_walk_forward(
    market_data: MarketData,
    parameter_candidates: Sequence[Mapping[str, Any]],
    evaluator: BacktestEvaluator,
    *,
    train_size: int,
    test_size: int,
    step_size: int | None = None,
    mode: SplitMode = "expanding",
    metric_name: str = "sharpe",
    maximize_metric: bool = True,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
) -> tuple[WalkForwardResult, ...]:
    """Select the best candidate on each train window and evaluate it on test.

    The callback receives only the data slice for the current phase: train
    candidates never see test bars, and the selected candidate is re-run using
    only test bars. The caller is responsible for making its evaluator
    deterministic and for generating positions causally within each slice.
    """
    if not parameter_candidates:
        raise ValueError("parameter_candidates cannot be empty.")
    if metric_name not in _METRIC_NAMES:
        raise ValueError(f"Unknown performance metric: {metric_name}.")
    if not isinstance(maximize_metric, bool):
        raise ValueError("maximize_metric must be a boolean.")
    if not callable(evaluator):
        raise ValueError("evaluator must be callable.")

    windows = generate_time_splits(
        market_data, train_size, test_size, step_size, mode
    )
    results: list[WalkForwardResult] = []
    for window in windows:
        train_data = slice_market_data(
            market_data, window.train_start, window.train_end
        )
        test_data = slice_market_data(
            market_data, window.test_start, window.test_end
        )
        evaluated: list[tuple[Mapping[str, Any], PerformanceMetrics]] = []
        warnings: list[str] = []
        for parameters in parameter_candidates:
            train_result = evaluator(train_data, parameters)
            metrics = calculate_metrics(
                train_result, periods_per_year, risk_free_rate
            )
            metric_value = getattr(metrics, metric_name)
            if metric_value is not None and math.isfinite(metric_value):
                evaluated.append((parameters, metrics))

        if not evaluated:
            results.append(
                WalkForwardResult(
                    window=window,
                    evaluated_parameters=tuple(parameter_candidates),
                    selected_parameters=None,
                    metric_name=metric_name,
                    maximize_metric=maximize_metric,
                    in_sample_metrics=None,
                    out_of_sample_metrics=None,
                    warnings=(
                        f"No candidate produced a finite {metric_name} metric.",
                    ),
                )
            )
            continue

        select = max if maximize_metric else min
        selected_parameters, in_sample_metrics = select(
            evaluated,
            key=lambda item: getattr(item[1], metric_name),
        )
        test_result = evaluator(test_data, selected_parameters)
        out_of_sample_metrics = calculate_metrics(
            test_result, periods_per_year, risk_free_rate
        )
        if getattr(out_of_sample_metrics, metric_name) is None:
            warnings.append(
                f"Out-of-sample {metric_name} is undefined for this window."
            )
        results.append(
            WalkForwardResult(
                window=window,
                evaluated_parameters=tuple(parameter_candidates),
                selected_parameters=selected_parameters,
                metric_name=metric_name,
                maximize_metric=maximize_metric,
                in_sample_metrics=in_sample_metrics,
                out_of_sample_metrics=out_of_sample_metrics,
                warnings=tuple(warnings),
            )
        )
    return tuple(results)
