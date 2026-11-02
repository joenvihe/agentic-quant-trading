"""Descarga, valida y persiste el historial diario de un ticker."""

import argparse
from pathlib import Path
import sys
from collections.abc import Sequence

from config.logging_config import configure_logging
from config.settings import Settings
from data.engine import run_market_data_engine
from data.market_data import MarketBar, MarketDataError
from data.providers.yahoo_finance import YahooFinanceProvider


def _print_summary(ticker: str, bars: Sequence[MarketBar], path: Path) -> None:
    first = bars[0]
    latest = bars[-1]
    print(f"Ticker: {ticker}")
    print(f"Registros recuperados: {len(bars)}")
    print(f"Periodo: {first.timestamp.date()} - {latest.timestamp.date()}")
    print(f"Último cierre: {latest.close:.4f}")
    print(f"Ruta persistida: {path.resolve()}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Descarga y valida datos históricos diarios OHLCV."
    )
    parser.add_argument("ticker", help="Símbolo del activo, por ejemplo SPY.")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    configure_logging(settings)
    try:
        result = run_market_data_engine(
            args.ticker,
            YahooFinanceProvider(),
            settings.data_dir,
        )
    except (MarketDataError, OSError) as exc:
        print(f"Error al obtener datos de mercado: {exc}", file=sys.stderr)
        return 1

    _print_summary(result.market_data.ticker, result.market_data.bars, result.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
