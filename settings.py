"""Configuración centralizada y desacoplada del entorno."""

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Valores de configuración para los componentes del proyecto."""

    project_name: str = "Agentic Quant Trading"
    data_dir: Path = Path("data")
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        """Crea la configuración aplicando las variables de entorno disponibles."""
        return cls(
            data_dir=Path(os.getenv("AQT_DATA_DIR", "data")),
            log_level=os.getenv("AQT_LOG_LEVEL", "INFO").upper(),
        )
