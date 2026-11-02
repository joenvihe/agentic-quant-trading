"""Cálculo determinista de features cuantitativas sobre datos OHLCV normalizados."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import math
from statistics import fmean, pstdev

from data.market_data import MarketData


_RETURN_WINDOWS = {
    "return_1m": 21,
    "return_3m": 63,
    "return_6m": 126,
    "return_12m": 252,
}
_LONG_WINDOW = 252
_BOLLINGER_WINDOW = 20
_REALIZED_VOLATILITY_WINDOW = 20
_AVERAGE_VOLUME_WINDOW = 20
FEATURE_NAMES = (
    "sma_20",
    "sma_50",
    "sma_100",
    "sma_200",
    "ema_20",
    "ema_50",
    "rsi_2",
    "rsi_14",
    *_RETURN_WINDOWS,
    "atr_14",
    "realized_volatility_20",
    "bollinger_upper_20",
    "bollinger_middle_20",
    "bollinger_lower_20",
    "bollinger_band_width_20",
    "average_volume_20",
    "relative_volume_20",
    "distance_from_52w_high",
    "rolling_drawdown_52w",
)


class FeatureError(Exception):
    """Error base del cálculo de features."""


@dataclass(frozen=True)
class FeatureRow:
    """Features de una barra, en el mismo orden que los datos de mercado."""

    timestamp: datetime
    values: Mapping[str, float | None]


@dataclass(frozen=True)
class FeatureSeries:
    """Serie completa de features para un ticker."""

    ticker: str
    rows: tuple[FeatureRow, ...]


def _rolling_mean(values: list[float], window: int, index: int) -> float | None:
    start = index - window + 1
    if start < 0:
        return None
    return fmean(values[start : index + 1])


def _ema(values: list[float], window: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) < window:
        return result

    current = fmean(values[:window])
    result[window - 1] = current
    multiplier = 2 / (window + 1)
    for index in range(window, len(values)):
        current = (values[index] - current) * multiplier + current
        result[index] = current
    return result


def _rsi(values: list[float], window: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) <= window:
        return result

    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain = fmean(gains[:window])
    average_loss = fmean(losses[:window])

    def rsi_value(gain: float, loss: float) -> float:
        if loss == 0:
            return 50.0 if gain == 0 else 100.0
        if gain == 0:
            return 0.0
        return 100 - 100 / (1 + gain / loss)

    result[window] = rsi_value(average_gain, average_loss)
    for index in range(window + 1, len(values)):
        change_index = index - 1
        average_gain = (
            average_gain * (window - 1) + gains[change_index]
        ) / window
        average_loss = (
            average_loss * (window - 1) + losses[change_index]
        ) / window
        result[index] = rsi_value(average_gain, average_loss)
    return result


def _atr(
    highs: list[float], lows: list[float], closes: list[float], window: int
) -> list[float | None]:
    result: list[float | None] = [None] * len(closes)
    if len(closes) <= window:
        return result

    true_ranges: list[float] = []
    for index in range(1, len(closes)):
        true_ranges.append(
            max(
                highs[index] - lows[index],
                abs(highs[index] - closes[index - 1]),
                abs(lows[index] - closes[index - 1]),
            )
        )
    if len(true_ranges) < window:
        return result

    current = fmean(true_ranges[:window])
    result[window] = current
    for index in range(window + 1, len(closes)):
        true_range = true_ranges[index - 1]
        current = (current * (window - 1) + true_range) / window
        result[index] = current
    return result


def calculate_features(market_data: MarketData) -> FeatureSeries:
    """Calcula features por barra sin descargar ni modificar datos de mercado.

    Los períodos mensuales y anuales se aproximan con 21 y 252 sesiones,
    respectivamente. Los campos que aún no tienen historial suficiente son None.
    """
    if not market_data.bars:
        raise FeatureError("No hay barras de mercado para calcular features.")

    closes = [bar.close for bar in market_data.bars]
    highs = [bar.high for bar in market_data.bars]
    lows = [bar.low for bar in market_data.bars]
    volumes = [bar.volume for bar in market_data.bars]
    emas = {window: _ema(closes, window) for window in (20, 50)}
    rsi_values = {window: _rsi(closes, window) for window in (2, 14)}
    atr_values = _atr(highs, lows, closes, 14)

    log_returns: list[float | None] = [None]
    for index in range(1, len(closes)):
        log_returns.append(math.log(closes[index] / closes[index - 1]))

    rows: list[FeatureRow] = []
    for index, bar in enumerate(market_data.bars):
        values: dict[str, float | None] = {
            "sma_20": _rolling_mean(closes, 20, index),
            "sma_50": _rolling_mean(closes, 50, index),
            "sma_100": _rolling_mean(closes, 100, index),
            "sma_200": _rolling_mean(closes, 200, index),
            "ema_20": emas[20][index],
            "ema_50": emas[50][index],
            "rsi_2": rsi_values[2][index],
            "rsi_14": rsi_values[14][index],
        }

        for name, window in _RETURN_WINDOWS.items():
            values[name] = (
                closes[index] / closes[index - window] - 1
                if index >= window
                else None
            )

        values["atr_14"] = atr_values[index]
        realized_start = index - _REALIZED_VOLATILITY_WINDOW + 1
        if realized_start >= 1:
            window_returns = [
                value
                for value in log_returns[realized_start : index + 1]
                if value is not None
            ]
            values["realized_volatility_20"] = (
                pstdev(window_returns) * math.sqrt(252)
            )
        else:
            values["realized_volatility_20"] = None

        bollinger_mean = _rolling_mean(closes, _BOLLINGER_WINDOW, index)
        if bollinger_mean is None:
            values["bollinger_upper_20"] = None
            values["bollinger_middle_20"] = None
            values["bollinger_lower_20"] = None
            values["bollinger_band_width_20"] = None
        else:
            start = index - _BOLLINGER_WINDOW + 1
            deviation = pstdev(closes[start : index + 1])
            upper = bollinger_mean + 2 * deviation
            lower = bollinger_mean - 2 * deviation
            values["bollinger_upper_20"] = upper
            values["bollinger_middle_20"] = bollinger_mean
            values["bollinger_lower_20"] = lower
            values["bollinger_band_width_20"] = (
                (upper - lower) / bollinger_mean if bollinger_mean != 0 else None
            )

        average_volume = _rolling_mean(volumes, _AVERAGE_VOLUME_WINDOW, index)
        values["average_volume_20"] = average_volume
        values["relative_volume_20"] = (
            bar.volume / average_volume
            if average_volume is not None and average_volume != 0
            else None
        )

        high_start = index - _LONG_WINDOW + 1
        if high_start < 0:
            values["distance_from_52w_high"] = None
            values["rolling_drawdown_52w"] = None
        else:
            rolling_high = max(highs[high_start : index + 1])
            rolling_close_high = max(closes[high_start : index + 1])
            values["distance_from_52w_high"] = bar.close / rolling_high - 1
            values["rolling_drawdown_52w"] = (
                bar.close / rolling_close_high - 1
            )

        rows.append(FeatureRow(timestamp=bar.timestamp, values=values))

    return FeatureSeries(ticker=market_data.ticker, rows=tuple(rows))
