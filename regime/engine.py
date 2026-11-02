"""Baseline determinista e interpretable de clasificación de régimen."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import math

from config.regime import RegimeThresholds
from features.engine import FeatureSeries


_METRIC_NAMES = (
    "sma_20",
    "sma_50",
    "sma_200",
    "return_1m",
    "return_3m",
    "return_6m",
    "return_12m",
    "realized_volatility_20",
    "atr_14",
    "bollinger_band_width_20",
    "distance_from_52w_high",
)


class RegimeError(Exception):
    """Error de entrada o cálculo en Market Regime Engine."""


@dataclass(frozen=True)
class RegimeAssessment:
    """Resultado estructurado de una evaluación de régimen."""

    ticker: str
    timestamp: datetime
    regime: str
    metrics: Mapping[str, float | None]
    evidence: Mapping[str, object]
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Representa el resultado con una estructura serializable a JSON."""
        return {
            "ticker": self.ticker,
            "timestamp": self.timestamp.isoformat(),
            "regime": self.regime,
            "metrics": dict(self.metrics),
            "evidence": dict(self.evidence),
            "reason_codes": list(self.reason_codes),
        }


def _read_metric(values: Mapping[str, float | None], name: str) -> float | None:
    value = values.get(name)
    if value is not None and not math.isfinite(value):
        raise RegimeError(f"La feature {name} no es finita.")
    return value


def detect_regime(
    feature_series: FeatureSeries,
    thresholds: RegimeThresholds,
) -> RegimeAssessment:
    """Evalúa direction, strength, volatility y confirmation por separado.

    La clasificación solo utiliza features ya calculadas por Quant Feature Engine.
    No genera señales, recomendaciones ni operaciones.
    """
    if not feature_series.rows:
        raise RegimeError(f"{feature_series.ticker}: no hay features disponibles.")

    latest = feature_series.rows[-1]
    raw_metrics = {
        name: _read_metric(latest.values, name) for name in _METRIC_NAMES
    }
    sma_20 = raw_metrics["sma_20"]
    sma_50 = raw_metrics["sma_50"]
    sma_200 = raw_metrics["sma_200"]
    return_1m = raw_metrics["return_1m"]
    return_3m = raw_metrics["return_3m"]
    return_6m = raw_metrics["return_6m"]
    return_12m = raw_metrics["return_12m"]
    realized_volatility = raw_metrics["realized_volatility_20"]
    atr_14 = raw_metrics["atr_14"]
    bollinger_width = raw_metrics["bollinger_band_width_20"]

    atr_to_sma20 = (
        atr_14 / sma_20
        if atr_14 is not None and sma_20 is not None and sma_20 != 0
        else None
    )
    if atr_to_sma20 is not None and not math.isfinite(atr_to_sma20):
        raise RegimeError("La razón ATR14/SMA20 no es finita.")
    metrics = {**raw_metrics, "atr_14_to_sma_20": atr_to_sma20}

    if sma_50 is None or sma_200 is None:
        direction = "UNKNOWN"
    elif sma_50 > sma_200:
        direction = "BULLISH"
    elif sma_50 < sma_200:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"

    bullish_criteria = {
        "return_1m_and_3m_positive": (
            return_1m is not None
            and return_3m is not None
            and return_1m > 0
            and return_3m > 0
        ),
        "sma_20_above_sma_50": (
            sma_20 is not None and sma_50 is not None and sma_20 > sma_50
        ),
        "inferred_price_above_sma_50": (
            sma_20 is not None
            and return_1m is not None
            and sma_50 is not None
            and sma_20 * (1 + return_1m) > sma_50
        ),
    }
    bearish_criteria = {
        "return_1m_and_3m_negative": (
            return_1m is not None
            and return_3m is not None
            and return_1m < 0
            and return_3m < 0
        ),
        "sma_20_below_sma_50": (
            sma_20 is not None and sma_50 is not None and sma_20 < sma_50
        ),
        "inferred_price_below_sma_50": (
            sma_20 is not None
            and return_1m is not None
            and sma_50 is not None
            and sma_20 * (1 + return_1m) < sma_50
        ),
    }
    bullish_agreements = sum(bullish_criteria.values())
    bearish_agreements = sum(bearish_criteria.values())
    if bullish_agreements >= thresholds.confirmation_min_agreements:
        confirmation = "CONFIRMED_BULLISH"
    elif bearish_agreements >= thresholds.confirmation_min_agreements:
        confirmation = "CONFIRMED_BEARISH"
    else:
        confirmation = "MIXED_OR_INSUFFICIENT"

    if return_6m is None or return_12m is None:
        strength = "UNKNOWN"
    elif return_6m >= thresholds.bull_strength_return_6m:
        strength = "STRONG_BULLISH"
    elif return_6m < 0 and return_12m < 0:
        strength = "BEARISH"
    else:
        strength = "NEUTRAL"

    available_volatility = [
        value for value in (realized_volatility, atr_to_sma20) if value is not None
    ]
    if not available_volatility:
        volatility = "UNKNOWN"
    elif (
        realized_volatility is not None
        and realized_volatility >= thresholds.chaotic_realized_volatility
    ) or (
        atr_to_sma20 is not None
        and atr_to_sma20 >= thresholds.chaotic_atr_to_sma20
    ):
        volatility = "CHAOTIC"
    elif (
        realized_volatility is not None
        and realized_volatility >= thresholds.elevated_realized_volatility
    ) or (
        atr_to_sma20 is not None
        and atr_to_sma20 >= thresholds.elevated_atr_to_sma20
    ):
        volatility = "ELEVATED"
    elif realized_volatility is not None and atr_to_sma20 is not None:
        volatility = "NORMAL"
    else:
        volatility = "PARTIALLY_KNOWN"

    is_range = (
        return_6m is not None
        and bollinger_width is not None
        and abs(return_6m) < thresholds.range_abs_return_6m
        and bollinger_width < thresholds.range_bollinger_width
    )

    if volatility == "CHAOTIC":
        regime = "CHAOTIC"
    elif direction == "BEARISH" and confirmation == "CONFIRMED_BEARISH":
        regime = "BEAR"
    elif (
        direction == "BULLISH"
        and confirmation == "CONFIRMED_BULLISH"
        and volatility == "ELEVATED"
    ):
        regime = "BULL_VOLATILE"
    elif (
        direction == "BULLISH"
        and confirmation == "CONFIRMED_BULLISH"
        and strength == "STRONG_BULLISH"
        and volatility == "NORMAL"
    ):
        regime = "BULL_STRONG"
    elif is_range:
        regime = "RANGE"
    else:
        regime = "TRANSITION"

    reason_codes: list[str] = []
    reason_codes.append(f"DIRECTION_{direction}")
    reason_codes.append(f"STRENGTH_{strength}")
    reason_codes.append(f"VOLATILITY_{volatility}")
    reason_codes.append(f"CONFIRMATION_{confirmation}")
    if regime == "CHAOTIC":
        if (
            realized_volatility is not None
            and realized_volatility >= thresholds.chaotic_realized_volatility
        ):
            reason_codes.append("REALIZED_VOLATILITY_AT_OR_ABOVE_CHAOTIC_THRESHOLD")
        if (
            atr_to_sma20 is not None
            and atr_to_sma20 >= thresholds.chaotic_atr_to_sma20
        ):
            reason_codes.append("ATR_TO_SMA20_AT_OR_ABOVE_CHAOTIC_THRESHOLD")
    elif regime == "BEAR":
        reason_codes.append("BEARISH_DIRECTION_AND_CONFIRMATION")
    elif regime == "BULL_VOLATILE":
        reason_codes.append("BULLISH_DIRECTION_WITH_ELEVATED_VOLATILITY")
    elif regime == "BULL_STRONG":
        reason_codes.append("BULLISH_DIRECTION_CONFIRMED_STRONG_AND_NORMAL_VOLATILITY")
    elif regime == "RANGE":
        reason_codes.append("SIX_MONTH_RETURN_AND_BOLLINGER_WIDTH_WITHIN_RANGE_LIMITS")
    else:
        reason_codes.append("REGIME_CRITERIA_MIXED_OR_INSUFFICIENT")

    evidence: dict[str, object] = {
        "direction": {
            "state": direction,
            "criterion": "sma_50 > sma_200 bullish; sma_50 < sma_200 bearish",
        },
        "strength": {
            "state": strength,
            "bullish_threshold_return_6m": thresholds.bull_strength_return_6m,
            "bullish_condition": (
                return_6m is not None
                and return_6m >= thresholds.bull_strength_return_6m
            ),
            "bearish_condition": (
                return_6m is not None
                and return_12m is not None
                and return_6m < 0
                and return_12m < 0
            ),
        },
        "volatility": {
            "state": volatility,
            "elevated_realized_threshold": thresholds.elevated_realized_volatility,
            "chaotic_realized_threshold": thresholds.chaotic_realized_volatility,
            "elevated_atr_ratio_threshold": thresholds.elevated_atr_to_sma20,
            "chaotic_atr_ratio_threshold": thresholds.chaotic_atr_to_sma20,
            "realized_volatility_elevated": (
                realized_volatility is not None
                and realized_volatility >= thresholds.elevated_realized_volatility
            ),
            "realized_volatility_chaotic": (
                realized_volatility is not None
                and realized_volatility >= thresholds.chaotic_realized_volatility
            ),
            "atr_ratio_elevated": (
                atr_to_sma20 is not None
                and atr_to_sma20 >= thresholds.elevated_atr_to_sma20
            ),
            "atr_ratio_chaotic": (
                atr_to_sma20 is not None
                and atr_to_sma20 >= thresholds.chaotic_atr_to_sma20
            ),
        },
        "confirmation": {
            "state": confirmation,
            "minimum_agreements": thresholds.confirmation_min_agreements,
            "bullish_agreements": bullish_agreements,
            "bearish_agreements": bearish_agreements,
            "bullish_criteria": bullish_criteria,
            "bearish_criteria": bearish_criteria,
            "inferred_price_note": (
                "Approximation: sma_20 * (1 + return_1m); not a close-price feature."
            ),
        },
        "range_condition": {
            "matched": is_range,
            "absolute_return_6m_limit": thresholds.range_abs_return_6m,
            "bollinger_width_limit": thresholds.range_bollinger_width,
        },
    }
    return RegimeAssessment(
        ticker=feature_series.ticker,
        timestamp=latest.timestamp,
        regime=regime,
        metrics=metrics,
        evidence=evidence,
        reason_codes=tuple(reason_codes),
    )
