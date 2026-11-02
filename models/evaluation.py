"""Classification metrics; these do not represent investment performance."""

from dataclasses import dataclass
import math
from typing import Sequence

from models.types import MLSignal


@dataclass(frozen=True)
class ClassificationMetrics:
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float | None
    confusion_matrix: tuple[tuple[int, int], tuple[int, int]]


def _roc_auc(labels: Sequence[int], scores: Sequence[float]) -> float | None:
    positive_count = sum(label == 1 for label in labels)
    negative_count = len(labels) - positive_count
    if not positive_count or not negative_count:
        return None
    ordered = sorted(zip(scores, labels))
    positive_rank_sum = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        average_rank = ((index + 1) + end) / 2
        positive_rank_sum += average_rank * sum(
            label == 1 for _, label in ordered[index:end]
        )
        index = end
    return (
        positive_rank_sum - positive_count * (positive_count + 1) / 2
    ) / (positive_count * negative_count)


def evaluate_classifier(
    y_true: Sequence[int], predictions: Sequence[MLSignal]
) -> ClassificationMetrics:
    if not y_true or len(y_true) != len(predictions):
        raise ValueError("Labels and predictions must be non-empty and equal length.")
    if any(label not in (0, 1) for label in y_true):
        raise ValueError("Labels must be binary values 0 or 1.")
    y_pred = [prediction.predicted_class for prediction in predictions]
    scores = [prediction.positive_probability for prediction in predictions]
    if any(not math.isfinite(score) or not 0 <= score <= 1 for score in scores):
        raise ValueError("Prediction probabilities must be finite and in [0, 1].")
    tn = sum(
        actual == 0 and predicted == 0
        for actual, predicted in zip(y_true, y_pred)
    )
    fp = sum(
        actual == 0 and predicted == 1
        for actual, predicted in zip(y_true, y_pred)
    )
    fn = sum(
        actual == 1 and predicted == 0
        for actual, predicted in zip(y_true, y_pred)
    )
    tp = sum(
        actual == 1 and predicted == 1
        for actual, predicted in zip(y_true, y_pred)
    )
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return ClassificationMetrics(
        accuracy=(tp + tn) / len(y_true),
        precision=precision,
        recall=recall,
        f1=f1,
        roc_auc=_roc_auc(y_true, scores),
        confusion_matrix=((tn, fp), (fn, tp)),
    )
