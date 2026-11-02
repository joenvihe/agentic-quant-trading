"""Carga, normalización, validación y almacenamiento de datos de mercado."""

from data.engine import MarketDataResult, run_market_data_engine
from data.market_data import (
    MarketBar,
    MarketData,
    MarketDataDownloadError,
    MarketDataError,
    MarketDataProvider,
    MarketDataValidationError,
    normalize_market_data,
    normalize_ticker,
)

__all__ = [
    "MarketBar",
    "MarketData",
    "MarketDataDownloadError",
    "MarketDataError",
    "MarketDataProvider",
    "MarketDataResult",
    "MarketDataValidationError",
    "normalize_market_data",
    "normalize_ticker",
    "run_market_data_engine",
]
"""Carga y gestión de datos."""
