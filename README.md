# Agentic Quant Trading

Proyecto educativo para construir progresivamente un sistema de investigación
de swing trading basado en Python, herramientas cuantitativas e IA agéntica.

## Alcance actual

Esta primera fase contiene únicamente la estructura y configuración iniciales
del núcleo cuantitativo. No implementa estrategias, ejecución de operaciones,
conexiones con brokers, envío de órdenes, uso de dinero real, LLMs ni agentes
autónomos.

## Requisitos

- Python 3.11 o posterior
- `pip`

## Instalación para desarrollo

Desde la raíz del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Pruebas

```powershell
python -m pytest
```

## Configuración

La configuración está centralizada en `config/settings.py` y puede ajustarse
mediante variables de entorno:

- `AQT_DATA_DIR`: directorio de datos (por defecto, `data`)
- `AQT_LOG_LEVEL`: nivel de logging (por defecto, `INFO`)

Para configurar el logging de la aplicación, se puede llamar
`config.logging_config.configure_logging()` explícitamente. Importar módulos
del proyecto no configura logging ni realiza operaciones con efectos
secundarios.

## Estructura

Consulta [`docs/architecture.md`](docs/architecture.md) para el propósito de
cada módulo y los límites actuales del proyecto.
