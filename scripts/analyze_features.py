"""Calcula y muestra las features más recientes de un ticker persistido."""

import argparse
import json
from collections.abc import Sequence
import sys

from config.settings import Settings
from data.market_data import MarketDataError, normalize_ticker
from data.storage import load_market_data, market_data_path
from features.engine import FeatureError, calculate_features


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Calcula features cuantitativas desde datos OHLCV locales."
    )
    parser.add_argument("ticker", help="Símbolo del activo, por ejemplo SPY.")
    args = parser.parse_args(argv)

    try:
        ticker = normalize_ticker(args.ticker)
        settings = Settings.from_env()
        path = market_data_path(settings.data_dir / "market_data", ticker)
        market_data = load_market_data(path, ticker)
        features = calculate_features(market_data)
    except (FeatureError, MarketDataError, OSError) as exc:
        print(f"Error al analizar features: {exc}", file=sys.stderr)
        return 1

    latest = features.rows[-1]
    print(
        json.dumps(
            {
                "ticker": features.ticker,
                "timestamp": latest.timestamp.isoformat(),
                "features": dict(latest.values),
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
