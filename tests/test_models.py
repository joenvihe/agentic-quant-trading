from datetime import datetime, timedelta, timezone

import pytest

from data.market_data import MarketBar, MarketData
from features.engine import FeatureRow, FeatureSeries
from models import (
    BaselineClassifier,
    DatasetError,
    ModelError,
    XGBoostClassifier,
    build_ml_dataset,
    evaluate_classifier,
    generate_direction_targets,
    temporal_train_test_split,
)
from models.preprocessing import fit_standardizer


START = datetime(2024, 1, 1, tzinfo=timezone.utc)


def sample_data(count: int = 60):
    closes = [100.0]
    for index in range(count - 1):
        closes.append(closes[-1] * (1.02 if index % 2 == 0 else 0.98))
    bars = tuple(
        MarketBar(
            timestamp=START + timedelta(days=index),
            open=close,
            high=close + 1,
            low=close - 1,
            close=close,
            volume=1000,
        )
        for index, close in enumerate(closes)
    )
    market_data = MarketData("SPY", bars)
    rows = tuple(
        FeatureRow(
            bar.timestamp,
            {
                "momentum": None if index == 0 else float(index % 2),
                "level": float(index),
            },
        )
        for index, bar in enumerate(bars)
    )
    return market_data, FeatureSeries("SPY", rows)


def make_dataset():
    market_data, features = sample_data()
    return build_ml_dataset(
        market_data,
        features,
        horizon=1,
        threshold=0,
        feature_names=("momentum", "level"),
    )


def test_forward_targets_have_separate_feature_and_target_timestamps() -> None:
    market_data, _ = sample_data(5)
    targets = generate_direction_targets(market_data, horizon=2, threshold=0)
    assert len(targets) == 3
    assert targets[0].feature_timestamp == market_data.bars[0].timestamp
    assert targets[0].target_timestamp == market_data.bars[2].timestamp
    expected = int(
        market_data.bars[2].close / market_data.bars[0].close - 1 > 0
    )
    assert targets[0].target == expected


def test_dataset_drops_missing_rows_and_rejects_missing_columns() -> None:
    market_data, features = sample_data(8)
    dataset = build_ml_dataset(
        market_data, features, 1, 0, feature_names=("momentum",)
    )
    assert dataset.samples[0].feature_timestamp == market_data.bars[1].timestamp
    broken = FeatureSeries(
        "SPY",
        tuple(
            FeatureRow(row.timestamp, {"momentum": row.values["momentum"]})
            for row in features.rows
        ),
    )
    with pytest.raises(DatasetError, match="missing"):
        build_ml_dataset(market_data, broken, 1, 0, feature_names=("not_present",))


def test_temporal_split_is_ordered_and_purges_overlapping_labels() -> None:
    split = temporal_train_test_split(make_dataset(), test_fraction=0.25)
    assert split.train_end < split.test_start
    assert all(sample.target_timestamp < split.test_start for sample in split.train)
    assert all(sample.feature_timestamp >= split.test_start for sample in split.test)


def test_baseline_scaler_uses_training_only_and_predictions_are_reproducible() -> None:
    split = temporal_train_test_split(make_dataset())
    scaler = fit_standardizer(split.train, ("momentum", "level"))
    changed_test_sample = split.test[-1]
    assert scaler.means[1] == pytest.approx(
        sum(sample.features["level"] for sample in split.train) / len(split.train)
    )
    assert changed_test_sample.features["level"] not in (
        scaler.means[1],
        scaler.scales[1],
    )

    first = BaselineClassifier(random_state=7).fit(split.train).predict(split.test)
    second = BaselineClassifier(random_state=7).fit(split.train).predict(split.test)
    assert first == second
    assert all(signal.model_name == "logistic_baseline" for signal in first)


def test_classifier_metrics_include_confusion_matrix_and_auc() -> None:
    split = temporal_train_test_split(make_dataset())
    predictions = (
        BaselineClassifier(random_state=5)
        .fit(split.train)
        .predict(split.test)
    )
    metrics = evaluate_classifier(
        [sample.target for sample in split.test],
        predictions,
    )
    assert 0 <= metrics.accuracy <= 1
    assert metrics.confusion_matrix[0][0] + metrics.confusion_matrix[0][1] > 0
    assert metrics.roc_auc is None or 0 <= metrics.roc_auc <= 1


def test_xgboost_is_seeded_and_emits_ml_signals_not_orders() -> None:
    split = temporal_train_test_split(make_dataset())
    first = XGBoostClassifier(
        random_state=11, n_estimators=5, max_depth=2
    ).fit(split.train).predict(split.test)
    second = XGBoostClassifier(
        random_state=11, n_estimators=5, max_depth=2
    ).fit(split.train).predict(split.test)
    assert first == second
    assert all(signal.model_name == "xgboost" for signal in first)
    assert all(not hasattr(signal, "weight") for signal in first)


def test_invalid_split_and_unfitted_prediction_are_rejected() -> None:
    with pytest.raises(DatasetError, match="test_fraction"):
        temporal_train_test_split(make_dataset(), test_fraction=1)
    split = temporal_train_test_split(make_dataset())
    with pytest.raises(ModelError, match="fitted"):
        BaselineClassifier(random_state=1).predict(split.test)
