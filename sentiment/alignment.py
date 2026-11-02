"""Align rolling news sentiment to feature timestamps using past news only."""

from datetime import timedelta

from features.engine import FeatureRow, FeatureSeries
from sentiment.aggregate import SentimentFeature, SentimentScorer, aggregate_sentiment
from sentiment.types import NewsItem


def align_sentiment(
    features: FeatureSeries,
    items: tuple[NewsItem, ...],
    scorer: SentimentScorer,
    lookback: timedelta,
) -> tuple[SentimentFeature, ...]:
    """Create one trailing sentiment feature per existing feature timestamp."""
    previous = None
    aligned: list[SentimentFeature] = []
    for row in features.rows:
        if row.timestamp.tzinfo is None or row.timestamp.utcoffset() is None:
            raise ValueError("Feature timestamps must be timezone-aware.")
        if previous is not None and row.timestamp <= previous:
            raise ValueError("Feature timestamps must be strictly increasing.")
        previous = row.timestamp
        aligned.append(
            aggregate_sentiment(
                items,
                scorer,
                features.ticker,
                row.timestamp,
                lookback,
            )
        )
    return tuple(aligned)


def merge_sentiment_features(
    features: FeatureSeries,
    sentiment_features: tuple[SentimentFeature, ...],
) -> FeatureSeries:
    """Append numeric sentiment columns to the matching feature rows."""
    if len(features.rows) != len(sentiment_features):
        raise ValueError("Sentiment and feature series must have equal length.")
    rows: list[FeatureRow] = []
    for row, sentiment in zip(features.rows, sentiment_features):
        if (
            sentiment.symbol.strip().upper() != features.ticker.strip().upper()
            or sentiment.timestamp != row.timestamp
        ):
            raise ValueError(
                "Sentiment entries must align with feature ticker and time."
            )
        values = dict(row.values)
        values.update(
            {
                "sentiment_compound": sentiment.compound_score,
                "sentiment_news_count": float(sentiment.news_count),
                "sentiment_dispersion": sentiment.dispersion,
            }
        )
        rows.append(FeatureRow(timestamp=row.timestamp, values=values))
    return FeatureSeries(ticker=features.ticker, rows=tuple(rows))
