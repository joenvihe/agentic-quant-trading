"""Descarga OHLCV con Data Engine y rankea momentum entre tickers."""

import argparse
from collections.abc import Sequence
import sys

from config.momentum import MomentumWeights
from config.settings import Settings
from data.engine import run_market_data_engine
from data.market_data import MarketDataError, normalize_ticker
from data.providers.yahoo_finance import YahooFinanceProvider
from factors.momentum import MomentumRank, MomentumRankingError, rank_momentum
from features.engine import FeatureError, FeatureSeries, calculate_features


def _print_ranking(ranking: tuple[MomentumRank, ...]) -> None:
    print("Rank | Ticker | 1M | 3M | 6M | 12M | Score")
    print("-----|--------|----|----|----|-----|------")
    for item in ranking:
        print(
            f"{item.rank:>4} | {item.ticker:<6} | "
            f"{item.momentum_1m:>7.2%} | {item.momentum_3m:>7.2%} | "
            f"{item.momentum_6m:>7.2%} | {item.momentum_12m:>7.2%} | "
            f"{item.composite_score:>6.2f}"
        )
    print("\nMomentum absoluto (retorno 12M > 0), percentil compuesto:")
    for item in ranking:
        absolute = "positivo" if item.absolute_momentum else "no positivo"
        print(
            f"{item.ticker}: absoluto {absolute}; relativo "
            f"1M/3M/6M/12M "
            f"{item.relative_momentum['1m']:.1f}/"
            f"{item.relative_momentum['3m']:.1f}/"
            f"{item.relative_momentum['6m']:.1f}/"
            f"{item.relative_momentum['12m']:.1f}; percentil compuesto "
            f"{item.percentile_rank:.1f}"
        )
    print("\nRanking cuantitativo; no es una recomendación financiera.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Descarga datos de mercado con Data Engine y rankea momentum "
            "entre los tickers indicados."
        )
    )
    parser.add_argument(
        "tickers",
        nargs="+",
        help="Uno o más símbolos, por ejemplo SPY QQQ IWM DIA.",
    )
    args = parser.parse_args(argv)

    try:
        tickers = [normalize_ticker(ticker) for ticker in args.tickers]
        if len(set(tickers)) != len(tickers):
            raise MomentumRankingError("La lista contiene tickers duplicados.")

        settings = Settings.from_env()
        weights = MomentumWeights.from_env()
        feature_series: dict[str, FeatureSeries] = {}
        for ticker in tickers:
            result = run_market_data_engine(
                ticker,
                YahooFinanceProvider(),
                settings.data_dir,
            )
            feature_series[ticker] = calculate_features(result.market_data)

        ranking = rank_momentum(feature_series, weights)
    except (
        FeatureError,
        MarketDataError,
        MomentumRankingError,
        OSError,
        ValueError,
    ) as exc:
        print(f"Error al rankear momentum: {exc}", file=sys.stderr)
        return 1

    _print_ranking(ranking)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
