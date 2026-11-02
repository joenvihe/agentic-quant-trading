"""Factor de momentum relativo para rankear un universo de activos."""

from collections.abc import Mapping
from dataclasses import dataclass
import math

from config.momentum import MomentumWeights
from features.engine import FeatureSeries


_HORIZONS = (
    ("1m", "return_1m", "weight_1m"),
    ("3m", "return_3m", "weight_3m"),
    ("6m", "return_6m", "weight_6m"),
    ("12m", "return_12m", "weight_12m"),
)


class MomentumRankingError(Exception):
    """Error del cálculo o la validación del ranking de momentum."""


@dataclass(frozen=True)
class MomentumRank:
    """Factor y ranking calculados para un activo del universo."""

    rank: int
    ticker: str
    momentum_1m: float
    momentum_3m: float
    momentum_6m: float
    momentum_12m: float
    absolute_momentum: bool
    relative_momentum: Mapping[str, float]
    percentile_rank: float
    composite_score: float


def _percentile_ranks(values: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    if len(ordered) == 1:
        return {ordered[0][0]: 100.0}

    ranks: dict[str, float] = {}
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][1] == ordered[start][1]:
            end += 1
        average_rank = (start + 1 + end) / 2
        percentile = (average_rank - 1) / (len(ordered) - 1) * 100
        for ticker, _ in ordered[start:end]:
            ranks[ticker] = percentile
        start = end
    return ranks


def rank_momentum(
    feature_series: Mapping[str, FeatureSeries],
    weights: MomentumWeights,
) -> tuple[MomentumRank, ...]:
    """Calcula momentum absoluto, relativo, percentil y score del universo.

    Momentum absoluto se considera positivo cuando el retorno de 12 meses es
    mayor que cero. El relativo es el percentil de cada horizonte entre los
    activos recibidos. El score compuesto es el promedio ponderado de esos
    cuatro percentiles, en escala 0-100.
    """
    if not feature_series:
        raise MomentumRankingError("El universo de activos está vacío.")

    latest_returns: dict[str, dict[str, float]] = {}
    for ticker, series in feature_series.items():
        if ticker != series.ticker:
            raise MomentumRankingError(
                f"El ticker de la clave {ticker} no coincide con la serie "
                f"{series.ticker}."
            )
        if not series.rows:
            raise MomentumRankingError(f"{ticker}: no hay features calculadas.")

        latest = series.rows[-1].values
        returns: dict[str, float] = {}
        for horizon, feature_name, _ in _HORIZONS:
            value = latest.get(feature_name)
            if value is None:
                raise MomentumRankingError(
                    f"{ticker}: historial insuficiente para momentum {horizon}."
                )
            if not math.isfinite(value):
                raise MomentumRankingError(
                    f"{ticker}: momentum {horizon} no es un número finito."
                )
            returns[horizon] = value
        latest_returns[ticker] = returns

    relative_by_horizon = {
        horizon: _percentile_ranks(
            {ticker: returns[horizon] for ticker, returns in latest_returns.items()}
        )
        for horizon, _, _ in _HORIZONS
    }

    scores: dict[str, float] = {}
    for ticker in latest_returns:
        weighted_percentiles = sum(
            (getattr(weights, weight_name) / weights.total)
            * relative_by_horizon[horizon][ticker]
            for horizon, _, weight_name in _HORIZONS
        )
        scores[ticker] = weighted_percentiles

    composite_percentiles = _percentile_ranks(scores)
    ordered_tickers = sorted(
        latest_returns,
        key=lambda ticker: (-scores[ticker], ticker),
    )
    return tuple(
        MomentumRank(
            rank=index,
            ticker=ticker,
            momentum_1m=latest_returns[ticker]["1m"],
            momentum_3m=latest_returns[ticker]["3m"],
            momentum_6m=latest_returns[ticker]["6m"],
            momentum_12m=latest_returns[ticker]["12m"],
            absolute_momentum=latest_returns[ticker]["12m"] > 0,
            relative_momentum={
                horizon: relative_by_horizon[horizon][ticker]
                for horizon, _, _ in _HORIZONS
            },
            percentile_rank=composite_percentiles[ticker],
            composite_score=scores[ticker],
        )
        for index, ticker in enumerate(ordered_tickers, start=1)
    )
