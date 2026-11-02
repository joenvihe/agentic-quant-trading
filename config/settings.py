"""Configuración centralizada y desacoplada del entorno."""

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Valores de configuración para los componentes del proyecto."""

    project_name: str = "Agentic Quant Trading"
    data_dir: Path = Path("data")
    research_workspace: Path = Path("research_workspace")
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        """Crea la configuración aplicando las variables de entorno disponibles."""
        return cls(
            data_dir=Path(os.getenv("AQT_DATA_DIR", "data")),
            research_workspace=Path(
                os.getenv("AQT_RESEARCH_WORKSPACE", "research_workspace")
            ),
            log_level=os.getenv("AQT_LOG_LEVEL", "INFO").upper(),
        )
