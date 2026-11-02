"""VADER-based compound sentiment scoring."""

from sentiment.aggregate import SentimentScorer


class VaderSentimentScorer:
    """Lazily construct VADER so importing this module has no side effects."""

    def __init__(self) -> None:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        except ImportError as exc:
            raise ImportError(
                "VADER is required for VaderSentimentScorer; install the "
                "'vaderSentiment' project dependency."
            ) from exc
        self._analyzer = SentimentIntensityAnalyzer()

    def score(self, text: str) -> float:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text cannot be empty.")
        return float(self._analyzer.polarity_scores(text)["compound"])
