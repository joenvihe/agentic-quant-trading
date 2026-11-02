"""Leakage-aware supervised classification for quantitative research."""

from models.baseline import BaselineClassifier
from models.datasets import (
    DatasetError,
    DatasetSplit,
    DatasetSample,
    MLDataset,
    build_ml_dataset,
    temporal_train_test_split,
)
from models.evaluation import ClassificationMetrics, evaluate_classifier
from models.targets import DirectionTarget, generate_direction_targets
from models.types import MLSignal, ModelError
from models.xgboost_model import XGBoostClassifier

__all__ = [
    "BaselineClassifier",
    "ClassificationMetrics",
    "DatasetError",
    "DatasetSample",
    "DatasetSplit",
    "DirectionTarget",
    "MLDataset",
    "MLSignal",
    "ModelError",
    "XGBoostClassifier",
    "build_ml_dataset",
    "evaluate_classifier",
    "generate_direction_targets",
    "temporal_train_test_split",
]
