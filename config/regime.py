"""Thresholds visibles y configurables del baseline de Market Regime Engine."""

from dataclasses import dataclass
import math
import os


@dataclass(frozen=True)
class RegimeThresholds:
    """Umbrales iniciales aprobados para la clasificación determinista."""

    bull_strength_return_6m: float = 0.10
    range_abs_return_6m: float = 0.10
    range_bollinger_width: float = 0.10
    elevated_realized_volatility: float = 0.30
    chaotic_realized_volatility: float = 0.45
    elevated_atr_to_sma20: float = 0.02
    chaotic_atr_to_sma20: float = 0.03
    confirmation_min_agreements: int = 2

    def __post_init__(self) -> None:
        values = (
            self.bull_strength_return_6m,
            self.range_abs_return_6m,
            self.range_bollinger_width,
            self.elevated_realized_volatility,
            self.chaotic_realized_volatility,
            self.elevated_atr_to_sma20,
            self.chaotic_atr_to_sma20,
        )
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("Los thresholds de régimen deben ser finitos y no negativos.")
        if self.chaotic_realized_volatility < self.elevated_realized_volatility:
            raise ValueError(
                "El threshold caótico de volatilidad realizada debe ser >= al elevado."
            )
        if self.chaotic_atr_to_sma20 < self.elevated_atr_to_sma20:
            raise ValueError("El threshold ATR caótico debe ser >= al elevado.")
        if not 1 <= self.confirmation_min_agreements <= 3:
            raise ValueError("Los acuerdos mínimos de confirmación deben estar entre 1 y 3.")

    @classmethod
    def from_env(cls) -> "RegimeThresholds":
        """Lee todos los thresholds opcionales del entorno."""
        try:
            return cls(
                bull_strength_return_6m=float(
                    os.getenv("AQT_REGIME_BULL_STRENGTH_RETURN_6M", "0.10")
                ),
                range_abs_return_6m=float(
                    os.getenv("AQT_REGIME_RANGE_ABS_RETURN_6M", "0.10")
                ),
                range_bollinger_width=float(
                    os.getenv("AQT_REGIME_RANGE_BOLLINGER_WIDTH", "0.10")
                ),
                elevated_realized_volatility=float(
                    os.getenv("AQT_REGIME_ELEVATED_REALIZED_VOLATILITY", "0.30")
                ),
                chaotic_realized_volatility=float(
                    os.getenv("AQT_REGIME_CHAOTIC_REALIZED_VOLATILITY", "0.45")
                ),
                elevated_atr_to_sma20=float(
                    os.getenv("AQT_REGIME_ELEVATED_ATR_TO_SMA20", "0.02")
                ),
                chaotic_atr_to_sma20=float(
                    os.getenv("AQT_REGIME_CHAOTIC_ATR_TO_SMA20", "0.03")
                ),
                confirmation_min_agreements=int(
                    os.getenv("AQT_REGIME_CONFIRMATION_MIN_AGREEMENTS", "2")
                ),
            )
        except ValueError as exc:
            raise ValueError(
                "Las variables AQT_REGIME_* deben contener thresholds numéricos "
                "válidos y consistentes."
            ) from exc
