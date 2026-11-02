"""Configuración explícita de logging."""

import logging

from config.settings import Settings


def configure_logging(settings: Settings | None = None) -> None:
    """Configura el logging raíz según los ajustes proporcionados."""
    config = settings or Settings.from_env()
    level = getattr(logging, config.log_level, None)
    if not isinstance(level, int):
        raise ValueError(f"Nivel de logging no válido: {config.log_level}")

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
