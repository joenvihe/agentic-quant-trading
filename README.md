# Agentic Quant Trading

Proyecto educativo para construir progresivamente un sistema de investigación
de swing trading basado en Python, herramientas cuantitativas e IA agéntica.

## Alcance actual: Market Data, Feature y Momentum Engines v0.1

Market Data Engine descarga OHLCV diario de Yahoo Finance, normaliza y valida
las barras y las guarda localmente como CSV. Quant Feature Engine calcula
indicadores deterministas desde ese modelo normalizado. Momentum Engine usa
esas features para rankear un universo; no genera señales ni operaciones.

No se implementan estrategias, backtesting, ejecución de operaciones, broker,
agentes, LLMs ni LangGraph.

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

## Descargar datos

```powershell
python -m scripts.download_market_data SPY
```

Los datos se guardan en `data/market_data/SPY.csv` por defecto. Se puede cambiar
el directorio raíz mediante `AQT_DATA_DIR`.

Yahoo Finance es una fuente gratuita de terceros, no oficial y sin garantía de
disponibilidad ni estabilidad de API. La descarga necesita conexión a Internet;
el comando termina con error si el proveedor no entrega datos válidos. El
historial es diario y usa el máximo período que Yahoo tenga disponible.

## Pruebas

```powershell
python -m pytest
```

Las pruebas usan datos sintéticos deterministas y no contactan Yahoo Finance.

## Rankear momentum

```powershell
python -m scripts.rank_momentum SPY QQQ IWM DIA
```

El comando recupera datos reales mediante Market Data Engine y muestra los
retornos de 1M/3M/6M/12M y un score compuesto de percentiles relativos. El
momentum absoluto se define como retorno 12M positivo. Los pesos del score son
iguales por defecto y configurables con `AQT_MOMENTUM_WEIGHT_1M`,
`AQT_MOMENTUM_WEIGHT_3M`, `AQT_MOMENTUM_WEIGHT_6M` y
`AQT_MOMENTUM_WEIGHT_12M`. El ranking es un factor cuantitativo, no una
recomendación financiera.

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
