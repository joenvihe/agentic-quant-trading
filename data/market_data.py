"""Tipos y validación del contrato común de datos OHLCV."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
import math
from numbers import Number
import re
from typing import Protocol


_TICKER_PATTERN = re.compile(r"^[A-Z0-9^][A-Z0-9.^=_-]{0,19}$")
_REQUIRED_FIELDS = ("timestamp", "open", "high", "low", "close", "volume")
_PRICE_FIELDS = ("open", "high", "low", "close")


class MarketDataError(Exception):
    """Error base del flujo de datos de mercado."""


class MarketDataDownloadError(MarketDataError):
    """El proveedor no pudo devolver datos utilizables."""


class MarketDataValidationError(MarketDataError):
    """Los datos recibidos no cumplen el contrato OHLCV."""


@dataclass(frozen=True)
class MarketBar:
    """Una barra diaria normalizada."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    adjusted_close: float | None = None


@dataclass(frozen=True)
class MarketData:
    """Serie temporal validada para un ticker."""

    ticker: str
    bars: tuple[MarketBar, ...]


class MarketDataProvider(Protocol):
    """Interfaz que deben implementar las fuentes de datos intercambiables."""

    def fetch(self, ticker: str) -> Iterable[Mapping[str, object]]:
        """Devuelve filas con campos normalizados y un timestamp."""


def normalize_ticker(ticker: str) -> str:
    """Normaliza el símbolo y evita usarlo como ruta de archivo arbitraria."""
    normalized = ticker.strip().upper()
    if not _TICKER_PATTERN.fullmatch(normalized):
        raise MarketDataValidationError(f"Ticker no válido: {ticker!r}")
    return normalized


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, datetime) and value != value:
        return True
    if isinstance(value, Number) and not isinstance(value, bool):
        try:
            return math.isnan(float(value))
        except (OverflowError, TypeError, ValueError):
            return False
    return False


def _parse_timestamp(value: object, row_number: int) -> datetime:
    if _is_missing(value):
        raise MarketDataValidationError(
            f"Fila {row_number}: falta el valor requerido 'timestamp'."
        )

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day)
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise MarketDataValidationError(
                f"Fila {row_number}: timestamp no válido: {value!r}."
            ) from exc
    else:
        raise MarketDataValidationError(
            f"Fila {row_number}: tipo de timestamp no válido: {type(value).__name__}."
        )

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_number(value: object, field: str, row_number: int) -> float:
    if _is_missing(value):
        raise MarketDataValidationError(
            f"Fila {row_number}: falta el valor requerido '{field}'."
        )
    if isinstance(value, bool):
        raise MarketDataValidationError(
            f"Fila {row_number}: '{field}' debe ser numérico, no booleano."
        )
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MarketDataValidationError(
            f"Fila {row_number}: '{field}' no es un número válido: {value!r}."
        ) from exc
    if not math.isfinite(number):
        raise MarketDataValidationError(
            f"Fila {row_number}: '{field}' debe ser un número finito."
        )
    return number


def normalize_market_data(
    ticker: str, rows: Iterable[Mapping[str, object]]
) -> MarketData:
    """Valida las filas en su orden original y construye el modelo común."""
    normalized_ticker = normalize_ticker(ticker)
    records = list(rows)
    if not records:
        raise MarketDataDownloadError(
            f"El proveedor no devolvió barras históricas para {normalized_ticker}."
        )

    has_adjusted_close = any("adjusted_close" in row for row in records)
    bars: list[MarketBar] = []
    seen_timestamps: set[datetime] = set()
    previous_timestamp: datetime | None = None

    for row_number, row in enumerate(records, start=1):
        missing_fields = [field for field in _REQUIRED_FIELDS if field not in row]
        if missing_fields:
            raise MarketDataValidationError(
                f"Fila {row_number}: faltan columnas requeridas: "
                f"{', '.join(missing_fields)}."
            )

        timestamp = _parse_timestamp(row["timestamp"], row_number)
        if timestamp in seen_timestamps:
            raise MarketDataValidationError(
                f"Fila {row_number}: timestamp duplicado {timestamp.isoformat()}."
            )
        if previous_timestamp is not None and timestamp < previous_timestamp:
            raise MarketDataValidationError(
                f"Fila {row_number}: timestamp desordenado "
                f"{timestamp.isoformat()} aparece después de "
                f"{previous_timestamp.isoformat()}."
            )
        seen_timestamps.add(timestamp)
        previous_timestamp = timestamp

        values = {
            field: _parse_number(row[field], field, row_number)
            for field in _PRICE_FIELDS
        }
        volume = _parse_number(row["volume"], "volume", row_number)
        adjusted_close: float | None = None
        if has_adjusted_close:
            if "adjusted_close" not in row:
                raise MarketDataValidationError(
                    f"Fila {row_number}: falta 'adjusted_close', presente en otras filas."
                )
            adjusted_close = _parse_number(
                row["adjusted_close"], "adjusted_close", row_number
            )

        for field, price in values.items():
            if price <= 0:
                raise MarketDataValidationError(
                    f"Fila {row_number}: '{field}' debe ser mayor que cero."
                )
        if adjusted_close is not None and adjusted_close <= 0:
            raise MarketDataValidationError(
                f"Fila {row_number}: 'adjusted_close' debe ser mayor que cero."
            )
        if volume < 0:
            raise MarketDataValidationError(
                f"Fila {row_number}: 'volume' no puede ser negativo."
            )

        opening = values["open"]
        high = values["high"]
        low = values["low"]
        close = values["close"]
        if high < low:
            raise MarketDataValidationError(
                f"Fila {row_number}: high ({high}) es menor que low ({low})."
            )
        if high < max(opening, close):
            raise MarketDataValidationError(
                f"Fila {row_number}: high debe ser mayor o igual que open y close."
            )
        if low > min(opening, close):
            raise MarketDataValidationError(
                f"Fila {row_number}: low debe ser menor o igual que open y close."
            )

        bars.append(
            MarketBar(
                timestamp=timestamp,
                open=opening,
                high=high,
                low=low,
                close=close,
                volume=volume,
                adjusted_close=adjusted_close,
            )
        )

    return MarketData(ticker=normalized_ticker, bars=tuple(bars))
