from datetime import datetime, timedelta, timezone

import pytest

from data.market_data import MarketBar, MarketData
from features.engine import FeatureRow, FeatureSeries
from models import build_ml_dataset
from sentiment import (
    FakeNewsProvider,
    NewsItem,
    VaderSentimentScorer,
    aggregate_sentiment,
    align_sentiment,
    merge_sentiment_features,
)


AS_OF = datetime(2025, 1, 3, tzinfo=timezone.utc)


def news_item(
    published_at: datetime, title: str, symbol: str = "SPY"
) -> NewsItem:
    return NewsItem(
        symbol=symbol,
        published_at=published_at,
        title=title,
        source="fixture",
    )


def test_vader_scores_positive_and_negative_text() -> None:
    scorer = VaderSentimentScorer()
    assert scorer.score("Great results, strong growth and record profits.") > 0
    negative = "Terrible results, massive losses and a disappointing outlook."
    assert scorer.score(negative) < 0


def test_fake_provider_and_aggregate_exclude_future_news() -> None:
    past = news_item(AS_OF - timedelta(days=1), "Strong growth and excellent results")
    future = news_item(AS_OF + timedelta(seconds=1), "Severe losses and failure")
    scorer = VaderSentimentScorer()

    fetched = FakeNewsProvider((past, future)).fetch(
        "spy", AS_OF - timedelta(days=7), AS_OF
    )
    aggregate = aggregate_sentiment(
        (past, future), scorer, "SPY", AS_OF, timedelta(days=7)
    )

    assert fetched == (past,)
    assert aggregate.news_count == 1
    assert aggregate.compound_score is not None and aggregate.compound_score > 0
    assert aggregate.period_start == past.published_at
    assert aggregate.period_end == past.published_at


def test_no_news_is_missing_not_zero_and_future_only_news_is_ignored() -> None:
    result = aggregate_sentiment(
        (news_item(AS_OF + timedelta(days=1), "Great news"),),
        VaderSentimentScorer(),
        "SPY",
        AS_OF,
        timedelta(days=5),
    )
    assert result.news_count == 0
    assert result.compound_score is None
    assert result.dispersion is None
    assert result.period_start is None
    assert result.period_end is None


def test_alignment_is_causal_at_each_feature_timestamp() -> None:
    first = AS_OF - timedelta(days=1)
    future = AS_OF + timedelta(days=1)
    feature_series = FeatureSeries(
        "SPY",
        (
            FeatureRow(first, {}),
            FeatureRow(AS_OF, {}),
        ),
    )
    aligned = align_sentiment(
        feature_series,
        (
            news_item(first, "Positive earnings beat"),
            news_item(future, "Negative surprise"),
        ),
        VaderSentimentScorer(),
        timedelta(days=7),
    )
    assert [feature.news_count for feature in aligned] == [1, 1]
    assert all(feature.period_end <= feature.timestamp for feature in aligned)
    merged = merge_sentiment_features(feature_series, aligned)
    assert merged.rows[0].values["sentiment_news_count"] == 1
    assert merged.rows[0].values["sentiment_compound"] is not None
    data = MarketData(
        "SPY",
        (
            MarketBar(first, 100, 101, 99, 100, 1000),
            MarketBar(AS_OF, 101, 102, 100, 101, 1000),
        ),
    )
    dataset = build_ml_dataset(
        data,
        merged,
        horizon=1,
        threshold=0,
        feature_names=("sentiment_compound", "sentiment_news_count"),
    )
    assert dataset.samples[0].features["sentiment_news_count"] == 1


def test_news_item_and_time_ranges_require_valid_values() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        NewsItem("SPY", datetime(2025, 1, 1), "title", "source")
    with pytest.raises(ValueError, match="lookback"):
        aggregate_sentiment((), VaderSentimentScorer(), "SPY", AS_OF, timedelta(0))
