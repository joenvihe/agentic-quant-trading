"""Orquestación del flujo descargar, validar, persistir y releer."""

from dataclasses import dataclass
from pathlib import Path

from data.market_data import (
    MarketData,
    MarketDataProvider,
    normalize_market_data,
    normalize_ticker,
)
from data.storage import load_market_data, save_market_data


@dataclass(frozen=True)
class MarketDataResult:
    """Resultado del flujo de mercado y ubicación persistida."""

    market_data: MarketData
    path: Path


def run_market_data_engine(
    ticker: str,
    provider: MarketDataProvider,
    data_dir: Path,
) -> MarketDataResult:
    """Ejecuta el flujo y devuelve solo datos leídos de la copia persistida."""
    normalized_ticker = normalize_ticker(ticker)
    rows = provider.fetch(normalized_ticker)
    market_data = normalize_market_data(normalized_ticker, rows)
    output_dir = data_dir / "market_data"
    path = save_market_data(market_data, output_dir)
    reloaded = load_market_data(path, normalized_ticker)
    return MarketDataResult(market_data=reloaded, path=path)
