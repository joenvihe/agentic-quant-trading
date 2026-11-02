# Agentic Quant Trading

Proyecto educativo para construir progresivamente un sistema de investigación
de swing trading basado en Python, herramientas cuantitativas e IA agéntica.

## Alcance actual: Data, Features, Factors, Signals y Strategies

Market Data Engine descarga OHLCV diario de Yahoo Finance, normaliza y valida
las barras y las guarda localmente como CSV. Quant Feature Engine calcula
indicadores deterministas desde ese modelo normalizado. Momentum Engine usa
esas features para rankear un universo; no genera señales ni operaciones.
Market Regime Engine clasifica por reglas deterministas dirección, fuerza,
volatilidad y confirmación; tampoco genera recomendaciones de mercado.
Signals transforma features disponibles en valores de señal explícitos.
Strategies evalúa señales o factores junto con el régimen y devuelve una
posición objetivo de investigación; un factor no se convierte directamente en
señal y una posición objetivo no es una orden.

No se implementan backtesting, ejecución de operaciones, broker, agentes, LLMs
ni LangGraph.

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

## Detectar régimen de mercado

```powershell
python -m scripts.detect_regime SPY
```

El comando obtiene datos mediante Market Data Engine, calcula las features
existentes y devuelve `regime`, `metrics`, `evidence` y `reason_codes` en JSON.
El baseline no usa machine learning, clustering, HMM ni LLM. Sus umbrales
iniciales están definidos y validados en `config/regime.py`; cada uno puede
modificarse desde el código o con su variable `AQT_REGIME_*` correspondiente:

| Variable | Valor inicial | Uso |
|---|---:|---|
| `AQT_REGIME_BULL_STRENGTH_RETURN_6M` | 0.10 | Retorno 6M para fuerza alcista |
| `AQT_REGIME_RANGE_ABS_RETURN_6M` | 0.10 | Límite estricto de retorno absoluto 6M para rango |
| `AQT_REGIME_RANGE_BOLLINGER_WIDTH` | 0.10 | Límite estricto de ancho Bollinger para rango |
| `AQT_REGIME_ELEVATED_REALIZED_VOLATILITY` | 0.30 | Volatilidad realizada anualizada elevada |
| `AQT_REGIME_CHAOTIC_REALIZED_VOLATILITY` | 0.45 | Volatilidad realizada anualizada caótica |
| `AQT_REGIME_ELEVATED_ATR_TO_SMA20` | 0.02 | ATR14/SMA20 elevado |
| `AQT_REGIME_CHAOTIC_ATR_TO_SMA20` | 0.03 | ATR14/SMA20 caótico |
| `AQT_REGIME_CONFIRMATION_MIN_AGREEMENTS` | 2 | Acuerdos mínimos de 3 criterios para confirmar |

La volatilidad usa condiciones inclusivas (`>=`); el rango usa límites estrictos
(`<`). Dirección compara SMA50 con SMA200. Confirmación requiere al menos dos
criterios de tres: retornos 1M y 3M alineados juntos, SMA20 contra SMA50, y una
aproximación `SMA20 * (1 + retorno 1M)` contra SMA50. Esta última es solo un proxy
construido a partir de features, no un precio de cierre. El resultado es una
clasificación descriptiva, no una recomendación de mercado.

## Generar informe de investigación

```powershell
python -m scripts.research_asset SPY
```

Este comando orquesta Market Data Engine, Quant Feature Engine, Momentum Engine
y Market Regime Engine. Resume datos y features disponibles; muestra `N/A`
cuando falta historial o una comparación de universo. El score y percentil de
momentum relativo aparecen como `N/A` para un único activo.

## Signals y Strategies

`signals.MovingAverageCrossSignal` consume las features ya calculadas del
`FeatureSeries`; por defecto compara SMA20 con SMA50. Solo se permiten períodos
SMA expuestos por el Feature Engine (20, 50, 100 y 200). Devuelve `LONG` cuando
la media rápida supera la lenta y `FLAT` en caso contrario o si falta el
historial requerido. No descarga datos ni genera órdenes.

`strategies.MovingAverageStrategy` mapea esas señales a una `TargetPosition`
con peso 1 para `LONG` y 0 para `FLAT`. `MomentumRegimeStrategy` consume el
`MomentumRank` existente y el `RegimeAssessment` existente: requiere momentum
absoluto positivo (retorno 12M > 0) y, por defecto, permite exposición solo en
`BULL_STRONG` o `BULL_VOLATILE`. La allowlist se puede configurar en su
constructor y se valida contra los estados reales del Market Regime Engine.
`StrategyRegistry` registra explícitamente instancias y rechaza nombres
duplicados.

Las señales y posiciones objetivo son resultados cuantitativos de
investigación, no instrucciones de ejecución. No hay órdenes ni conexión a
broker.

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
