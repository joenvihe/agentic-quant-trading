"""Temporal aggregation of sentiment scores without future-news leakage."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from statistics import fmean, pstdev
from typing import Protocol

from sentiment.types import NewsItem


class SentimentScorer(Protocol):
    def score(self, text: str) -> float:
        """Return a compound sentiment score in [-1, 1]."""


@dataclass(frozen=True)
class SentimentFeature:
    symbol: str
    timestamp: datetime
    compound_score: float | None
    news_count: int
    dispersion: float | None
    period_start: datetime | None
    period_end: datetime | None

    def __post_init__(self) -> None:
        _validate_timestamp(self.timestamp, "timestamp")
        if (
            not self.symbol.strip()
            or isinstance(self.news_count, bool)
            or not isinstance(self.news_count, int)
            or self.news_count < 0
        ):
            raise ValueError("Sentiment symbol and news_count are invalid.")
        if self.news_count == 0:
            if any(
                value is not None
                for value in (
                    self.compound_score,
                    self.dispersion,
                    self.period_start,
                    self.period_end,
                )
            ):
                raise ValueError("Empty sentiment windows must have missing metrics.")
            return
        if (
            self.compound_score is None
            or not math.isfinite(self.compound_score)
            or not -1.0 <= self.compound_score <= 1.0
        ):
            raise ValueError("compound_score must be finite and in [-1, 1].")
        if (
            self.dispersion is None
            or not math.isfinite(self.dispersion)
            or self.dispersion < 0
        ):
            raise ValueError("dispersion must be finite when news is present.")
        if self.period_start is None or self.period_end is None:
            raise ValueError(
                "News period boundaries are required when news is present."
            )
        _validate_timestamp(self.period_start, "period_start")
        _validate_timestamp(self.period_end, "period_end")
        if not self.period_start <= self.period_end <= self.timestamp:
            raise ValueError("Sentiment period must end no later than its timestamp.")


def _validate_timestamp(timestamp: datetime, field: str) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware.")


def aggregate_sentiment(
    items: Iterable[NewsItem],
    scorer: SentimentScorer,
    symbol: str,
    as_of: datetime,
    lookback: timedelta,
) -> SentimentFeature:
    """Average eligible article scores over [as_of-lookback, as_of]."""
    _validate_timestamp(as_of, "as_of")
    if not symbol.strip():
        raise ValueError("symbol cannot be empty.")
    if lookback <= timedelta(0):
        raise ValueError("lookback must be positive.")
    start = as_of - lookback
    eligible = sorted(
        (
            item
            for item in items
            if item.symbol.strip().upper() == symbol.strip().upper()
            and start <= item.published_at <= as_of
        ),
        key=lambda item: item.published_at,
    )
    if not eligible:
        return SentimentFeature(
            symbol=symbol.strip().upper(),
            timestamp=as_of,
            compound_score=None,
            news_count=0,
            dispersion=None,
            period_start=None,
            period_end=None,
        )

    scores: list[float] = []
    for item in eligible:
        article_text = (
            item.title if item.text is None else f"{item.title}. {item.text}"
        )
        score = scorer.score(article_text)
        if not math.isfinite(score) or not -1.0 <= score <= 1.0:
            raise ValueError("Sentiment scorer must return a finite score in [-1, 1].")
        scores.append(score)
    return SentimentFeature(
        symbol=symbol.strip().upper(),
        timestamp=as_of,
        compound_score=fmean(scores),
        news_count=len(scores),
        dispersion=pstdev(scores),
        period_start=eligible[0].published_at,
        period_end=eligible[-1].published_at,
    )
