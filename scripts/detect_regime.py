"""Descarga datos con Data Engine y emite una evaluación de régimen JSON."""

import argparse
import json
from collections.abc import Sequence
import sys

from config.regime import RegimeThresholds
from config.settings import Settings
from data.engine import run_market_data_engine
from data.market_data import MarketDataError, normalize_ticker
from data.providers.yahoo_finance import YahooFinanceProvider
from features.engine import FeatureError, calculate_features
from regime.engine import RegimeError, detect_regime


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Detecta un régimen de mercado determinista desde features calculadas."
        )
    )
    parser.add_argument("ticker", help="Símbolo del activo, por ejemplo SPY.")
    args = parser.parse_args(argv)

    try:
        ticker = normalize_ticker(args.ticker)
        settings = Settings.from_env()
        thresholds = RegimeThresholds.from_env()
        market_data = run_market_data_engine(
            ticker,
            YahooFinanceProvider(),
            settings.data_dir,
        ).market_data
        features = calculate_features(market_data)
        assessment = detect_regime(features, thresholds)
    except (
        FeatureError,
        MarketDataError,
        RegimeError,
        OSError,
        ValueError,
    ) as exc:
        print(f"Error al detectar régimen: {exc}", file=sys.stderr)
        return 1

    output = assessment.to_dict()
    output["disclaimer"] = (
        "Clasificación cuantitativa; no es una recomendación de mercado."
    )
    print(json.dumps(output, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
