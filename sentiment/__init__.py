"""Point-in-time news sentiment features."""

from sentiment.aggregate import SentimentFeature, SentimentScorer, aggregate_sentiment
from sentiment.alignment import align_sentiment, merge_sentiment_features
from sentiment.provider import FakeNewsProvider, NewsProvider
from sentiment.types import NewsItem
from sentiment.vader import VaderSentimentScorer

__all__ = [
    "FakeNewsProvider",
    "NewsItem",
    "NewsProvider",
    "SentimentFeature",
    "SentimentScorer",
    "VaderSentimentScorer",
    "aggregate_sentiment",
    "align_sentiment",
    "merge_sentiment_features",
]
