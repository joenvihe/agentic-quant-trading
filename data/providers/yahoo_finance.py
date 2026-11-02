"""Adaptador del proveedor gratuito Yahoo Finance mediante yfinance."""

from collections.abc import Iterable, Mapping
from typing import Any

import yfinance as yf
from yfinance.exceptions import YFException

from data.market_data import (
    MarketDataDownloadError,
    normalize_ticker,
)


class YahooFinanceProvider:
    """Obtiene el historial diario máximo disponible en Yahoo Finance."""

    def fetch(self, ticker: str) -> Iterable[Mapping[str, object]]:
        normalized_ticker = normalize_ticker(ticker)
        try:
            history = yf.Ticker(normalized_ticker).history(
                period="max",
                auto_adjust=False,
                actions=False,
                timeout=30,
                raise_errors=True,
            )
        except YFException as exc:
            raise MarketDataDownloadError(
                f"Yahoo Finance no pudo descargar datos para {normalized_ticker}: "
                f"{exc}"
            ) from exc
        if history.empty:
            raise MarketDataDownloadError(
                f"Yahoo Finance no devolvió datos históricos para "
                f"{normalized_ticker}."
            )

        frame = history.copy()
        if getattr(frame.columns, "nlevels", 1) > 1:
            frame.columns = [
                column[0] if isinstance(column, tuple) else column
                for column in frame.columns
            ]

        frame = frame.reset_index()
        column_names = {str(column).strip().casefold(): column for column in frame.columns}
        timestamp_column = next(
            (
                column_names[name]
                for name in ("date", "datetime", "timestamp")
                if name in column_names
            ),
            None,
        )
        if timestamp_column is None:
            raise MarketDataDownloadError(
                "La respuesta de Yahoo Finance no contiene una columna de fecha."
            )

        source_fields = {
            "open": ("open",),
            "high": ("high",),
            "low": ("low",),
            "close": ("close",),
            "adjusted_close": ("adj close", "adjusted close", "adjusted_close"),
            "volume": ("volume",),
        }
        selected_columns: dict[str, Any] = {}
        for field, candidates in source_fields.items():
            for candidate in candidates:
                if candidate in column_names:
                    selected_columns[field] = column_names[candidate]
                    break

        rows: list[dict[str, object]] = []
        for record in frame.to_dict(orient="records"):
            row: dict[str, object] = {"timestamp": record[timestamp_column]}
            for field, column in selected_columns.items():
                value = record[column]
                if field == "adjusted_close" and value is None:
                    continue
                row[field] = value
            rows.append(row)

        return rows
