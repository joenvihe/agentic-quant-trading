"""Persistencia local de series OHLCV validadas en CSV."""

import csv
from pathlib import Path

from data.market_data import (
    MarketData,
    MarketDataValidationError,
    normalize_market_data,
    normalize_ticker,
)


_BASE_FIELDS = ("timestamp", "open", "high", "low", "close", "volume")


def market_data_path(directory: Path, ticker: str) -> Path:
    """Devuelve una ruta segura y determinista para el historial del ticker."""
    return directory / f"{normalize_ticker(ticker)}.csv"


def save_market_data(market_data: MarketData, directory: Path) -> Path:
    """Guarda la serie validada en CSV y devuelve la ruta escrita."""
    directory.mkdir(parents=True, exist_ok=True)
    path = market_data_path(directory, market_data.ticker)
    has_adjusted_close = any(bar.adjusted_close is not None for bar in market_data.bars)
    fieldnames = list(_BASE_FIELDS)
    if has_adjusted_close:
        fieldnames.insert(5, "adjusted_close")

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for bar in market_data.bars:
            row: dict[str, object] = {
                "timestamp": bar.timestamp.isoformat(),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            if has_adjusted_close:
                row["adjusted_close"] = bar.adjusted_close
            writer.writerow(row)
    return path


def load_market_data(path: Path, ticker: str) -> MarketData:
    """Lee un CSV y vuelve a validar todas sus filas y su orden."""
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames or []
        missing_fields = [field for field in _BASE_FIELDS if field not in fieldnames]
        if missing_fields:
            raise MarketDataValidationError(
                f"El CSV {path} no contiene las columnas requeridas: "
                f"{', '.join(missing_fields)}."
            )
        return normalize_market_data(ticker, reader)
