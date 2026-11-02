"""Configuración de pesos para el score compuesto de momentum."""

from dataclasses import dataclass
import math
import os


@dataclass(frozen=True)
class MomentumWeights:
    """Pesos configurables para los cuatro horizontes de momentum."""

    weight_1m: float = 1.0
    weight_3m: float = 1.0
    weight_6m: float = 1.0
    weight_12m: float = 1.0

    def __post_init__(self) -> None:
        weights = (self.weight_1m, self.weight_3m, self.weight_6m, self.weight_12m)
        if any(not math.isfinite(weight) or weight < 0 for weight in weights):
            raise ValueError("Los pesos de momentum deben ser finitos y no negativos.")
        if not math.isfinite(sum(weights)) or sum(weights) == 0:
            raise ValueError("La suma de los pesos de momentum debe ser mayor que cero.")

    @property
    def total(self) -> float:
        return self.weight_1m + self.weight_3m + self.weight_6m + self.weight_12m

    @classmethod
    def from_env(cls) -> "MomentumWeights":
        """Lee pesos opcionales del entorno, manteniendo iguales los valores por defecto."""
        try:
            weights = (
                float(os.getenv("AQT_MOMENTUM_WEIGHT_1M", "1")),
                float(os.getenv("AQT_MOMENTUM_WEIGHT_3M", "1")),
                float(os.getenv("AQT_MOMENTUM_WEIGHT_6M", "1")),
                float(os.getenv("AQT_MOMENTUM_WEIGHT_12M", "1")),
            )
        except ValueError as exc:
            raise ValueError(
                "Los pesos AQT_MOMENTUM_WEIGHT_* deben ser números válidos."
            ) from exc
        return cls(*weights)
