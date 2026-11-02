"""Deterministic, offline market data provider for the version-base demo."""

from collections.abc import Iterable, Mapping
from datetime import date, datetime, time, timedelta, timezone
import math


class SyntheticMarketDataProvider:
    """Generate repeatable weekday OHLCV rows without network access."""

    def __init__(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> None:
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError("start_date cannot be after end_date.")
        self._end_date = end_date or (
            start_date + timedelta(days=450)
            if start_date is not None
            else date(2024, 10, 26)
        )
        self._start_date = (
            start_date - timedelta(days=420)
            if start_date is not None
            else self._end_date - timedelta(days=700)
        )

    def fetch(self, ticker: str) -> Iterable[Mapping[str, object]]:
        symbol_code = sum((index + 1) * ord(char) for index, char in enumerate(ticker))
        base_price = 80.0 + symbol_code % 70
        rows: list[dict[str, object]] = []
        current_date = self._start_date
        index = 0
        previous_close = base_price
        while current_date <= self._end_date:
            if current_date.weekday() < 5:
                close = (
                    base_price
                    + index * 0.035
                    + 3.0 * math.sin(index / 19.0 + symbol_code % 11)
                    + 1.2 * math.sin(index / 5.0 + symbol_code % 7)
                )
                opening = previous_close
                rows.append(
                    {
                        "timestamp": datetime.combine(
                            current_date, time.min, tzinfo=timezone.utc
                        ),
                        "open": opening,
                        "high": max(opening, close) + 0.5,
                        "low": min(opening, close) - 0.5,
                        "close": close,
                        "volume": 100_000.0 + (index * 37 + symbol_code) % 10_000,
                    }
                )
                previous_close = close
                index += 1
            current_date += timedelta(days=1)
        return rows
