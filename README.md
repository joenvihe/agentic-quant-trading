# Agentic Quant Trading

Proyecto educativo para construir progresivamente un sistema de investigación
de swing trading basado en Python, herramientas cuantitativas e IA agéntica.

## Alcance actual: investigación cuantitativa y portfolio

Market Data Engine descarga OHLCV diario de Yahoo Finance, normaliza y valida
las barras y las guarda localmente como CSV. Quant Feature Engine calcula
indicadores deterministas desde ese modelo normalizado. Momentum Engine usa
esas features para rankear un universo; no genera señales ni operaciones.
Market Regime Engine clasifica por reglas deterministas dirección, fuerza,
volatilidad y confirmación; tampoco genera recomendaciones de mercado.
Signals transforma features disponibles en valores de señal explícitos.
Strategies evalúa señales o factores junto con el régimen y devuelve una
posición objetivo de investigación; un factor no se convierte directamente
en señal y una posición objetivo no es una orden. Backtest y Evaluation
simulan posiciones históricas con ejecución causal y calculan métricas, sin
conectar brokers.
Portfolio ofrece asignación equal-weight y optimización de Sharpe máximo usando
series de retornos proporcionadas por el caller, sin descarga de precios.
Sentiment produce features point-in-time desde noticias suministradas por un
provider inyectado. Models construye targets futuros explícitos y entrena
clasificadores con particiones temporales; las predicciones son valores
`MLSignal`, no órdenes.

`execution.PaperBroker` simula órdenes market de compra/venta con precios
explícitos, long-only, comisión y slippage. No selecciona activos ni consume
señales o estrategias. No se conectan brokers reales, no se realizan llamadas
de red y no se usan credenciales. Las órdenes se resuelven inmediatamente; la
cancelación no aplica a este flujo síncrono.

El backtest y PaperBroker son simulaciones locales de investigación. No
gestionan dinero real ni se implementan agentes, LLMs o LangGraph.

Las capabilities existentes también se exponen como adapters tipados en
[`application/tools/`](application/tools/) para research, backtest,
comparación, risk, portfolio y reporting. Sus contratos y límites se describen
en [`docs/application_tools.md`](docs/application_tools.md).

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

## Pipeline de estrategia multi-activo

```powershell
python -m scripts.run_strategy_research SPY QQQ `
  --start-date 2023-01-01 `
  --end-date 2025-12-31 `
  --strategy moving_average `
  --strategy-param fast_window=20 `
  --strategy-param slow_window=50 `
  --initial-cash 100000 `
  --commission-bps 1 `
  --slippage-bps 2 `
  --output-dir reports/generated
```

El comando compone el universo explícito, Market Data Engine y su validación,
features, momentum cross-sectional, régimen, señal/estrategia, Risk Engine,
asignación equal-weight, backtests por activo, evaluación, benchmark, reportes
JSON/CSV/HTML y registro del experimento. Las estrategias son
`moving_average` y `momentum_regime`; sus parámetros se pasan con
`--strategy-param KEY=VALUE`. Añade `--debug` para obtener un traceback. El
código de salida es `0` si completa, `1` ante fallos de datos/ejecución y `2`
para argumentos inválidos.

El provider de mercado de producción usa Yahoo Finance; las pruebas inyectan
providers falsos y no acceden a Internet. Reportes y experimentos se escriben
en el directorio indicado. Multi-activo reutiliza el backtest existente de un
activo mediante sleeves de igual capital alineados a timestamps comunes; esto
se indica en el reporte. El límite de drawdown se evalúa por activo usando la
feature rolling 52W, no sobre una curva consolidada de cartera. Esta ruta es
investigación: no importa `PaperBroker`, no crea órdenes, no usa LLM y no
conecta brokers.
Los indicadores utilizan el historial anterior disponible para calentamiento,
pero el backtest y sus reportes quedan limitados al intervalo solicitado.

## Pruebas

```powershell
python -m pytest
```

Las pruebas usan datos sintéticos deterministas y no contactan Yahoo Finance.

## Sentiment y clasificación supervisada

```powershell
python -m pip install -e ".[dev]"
```

`sentiment.VaderSentimentScorer` calcula sentimiento compuesto de noticias
entregadas por el caller. `FakeNewsProvider` y las pruebas funcionan sin APIs
de noticias. La alineación utiliza solo publicaciones disponibles hasta cada
timestamp; ausencia de noticias se representa con valores no disponibles.
`merge_sentiment_features` agrega el score, conteo y dispersión a un
`FeatureSeries` para que puedan seleccionarse al crear el dataset.

Para modelos, construye `FeatureSeries` con `features.calculate_features` y
`MarketData` normalizado, crea el dataset y separa train/test cronológicamente:

```python
from features.engine import calculate_features
from models import (
    BaselineClassifier,
    build_ml_dataset,
    evaluate_classifier,
    temporal_train_test_split,
)

dataset = build_ml_dataset(market_data, calculate_features(market_data), 5, 0.01)
split = temporal_train_test_split(dataset, test_fraction=0.2)
model = BaselineClassifier(random_state=7).fit(split.train)
predictions = model.predict(split.test)
metrics = evaluate_classifier(
    [sample.target for sample in split.test], predictions
)
```

El target es 1 cuando el retorno futuro a `horizon` barras supera `threshold`;
las muestras cuya etiqueta se solapa con el test se purgan del train. El scaler
del baseline se ajusta únicamente con train. `XGBoostClassifier` ofrece el
modelo basado en árboles con `random_state` obligatorio. Las métricas
clasificatorias no son una medida de rentabilidad. Ni dataset ni modelos
generan órdenes, y no se integra ningún proveedor real de noticias.

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

## Backtest y evaluación

`backtest.run_backtest` recibe `MarketData` y posiciones objetivo con timestamp
de señal. Una posición calculada al cierre de `t` se ejecuta en la apertura del
siguiente bar; la última señal no se ejecuta al no existir un bar posterior.
La primera versión admite un activo, frecuencia diaria, posiciones long-only de
0 a 1, sin margen ni ventas cortas. Configura capital y costes con
`BacktestConfig(initial_cash=100_000, commission_bps=0, slippage_bps=0)`.

`evaluation.calculate_metrics` calcula Total Return, CAGR, volatilidad
anualizada, Sharpe, Sortino, Maximum Drawdown, Calmar, Win Rate, Profit Factor
y número de ejecuciones. `periods_per_year` (252 por defecto) y la tasa libre
de riesgo anual (`risk_free_rate`, 0 por defecto) son configurables. Las
métricas indefinidas, como Sharpe en una curva plana o Profit Factor sin
pérdidas cerradas, son `None`, no infinito. El benchmark Buy and Hold usa el
mismo modelo causal de entrada al siguiente bar.

Consulta [`docs/performance_metrics.md`](docs/performance_metrics.md) para las
definiciones, convenciones de costes y limitaciones.

## Walk-forward y Risk Engine

`evaluation.generate_time_splits` crea ventanas exclusivamente temporales,
expanding o rolling, por conteo de barras. `evaluation.run_walk_forward`
selecciona configuraciones candidatas optimizando una métrica configurable
(maximizar por defecto, o minimizar) solo en train y evalúa la elegida solo en
test. Proporciona un callback
`evaluate(MarketData, parameters) -> BacktestResult`; el callback recibe
exclusivamente los datos de la partición actual. Los splits no barajan datos y
requieren suficiente historial. Los resultados incluyen ventana, candidatos,
parámetro elegido, métricas in-sample/out-of-sample y warnings.

`risk.evaluate_risk` limita peso por activo y exposición total, puede ajustar
el peso según volatilidad realizada frente a un objetivo, y opcionalmente
bloquea nuevas posiciones cuando el drawdown alcanza `max_drawdown`. Devuelve
un `RiskDecision` con razones explícitas; no cambia precios, no selecciona
estrategias ni ejecuta órdenes. Estos controles todavía no están integrados
automáticamente en el backtest.

## Asignación y optimización de portfolio

`portfolio.EqualWeightAllocator` distribuye el capital por igual entre los
símbolos recibidos y valida los límites configurados.
`portfolio.estimate_covariance` estima la covarianza muestral desde series
alineadas de retornos normalizados. `portfolio.MaximumSharpeOptimizer`
maximiza Sharpe long-only, imponiendo `min_weight`, `max_weight` y suma de
pesos igual a uno; `periods_per_year` y `risk_free_rate` controlan la
anualización y el retorno libre de riesgo. No descarga precios ni conecta con
Risk, Backtest o brokers. Si la optimización falla o la volatilidad resultante
es cero, devuelve un resultado de fallo explícito, sin fallback a equal-weight.

El optimizador usa SciPy `SLSQP`, añadido como dependencia necesaria para
resolver de forma confiable el problema fraccional no lineal con restricciones.
La asignación equal-weight y la covarianza no dependen de SciPy. Las series de
retornos deben estar alineadas en frecuencia y rango temporal y reflejar solo
información disponible en el momento de la decisión.

## HMM Regime, Fundamental Engine y Universe Selection

El clasificador determinista de régimen permanece como baseline.
`regime.GaussianHMMRegime(random_state=42)` complementa ese resultado con un
Gaussian HMM de dos estados por defecto, usando log returns y rango diario
normalizado. Los IDs ocultos no se interpretan como alcistas/bajistas: se
acompañan de etiquetas derivadas de drift, volatilidad y número de observaciones.
`regime.compare_regimes` ofrece una comparación direccional descriptiva. El
resultado reporta el último timestamp del histórico recibido; el histórico debe
terminar en el corte temporal de la investigación. Para investigación histórica,
el caller debe ajustar con barras disponibles hasta ese corte solamente.

`fundamental.FundamentalDataProvider` recibe un corte `as_of` para que las
fuentes entreguen solo información disponible entonces.
`fetch_fundamental_snapshot` valida el límite temporal.
El timestamp del snapshot corresponde a cuándo la información estuvo disponible
públicamente, no solo al período fiscal reportado.
`calculate_fundamental_metrics` calcula ROC, Earnings Yield y P/E; datos
ausentes o denominadores no positivos resultan en `None`.
`rank_fundamentals(metrics, as_of)` produce un ranking combinado y rechaza
datos publicados después del corte, no señales ni órdenes.

`universe.StaticUniverseProvider` normaliza símbolos y elimina duplicados.
`universe.select_universe` recibe un corte `as_of` y aplica filtros configurables
de precio mínimo, histórico mínimo y datos faltantes; la capitalización mínima
solo filtra si hay un valor de capitalización disponible. Metadatos posteriores
al corte se rechazan. Cada activo rechazado incluye una razón. Providers de
datos son inyectados; no hay descargas automáticas. Un universo estático actual
no es automáticamente point-in-time ni está libre de survivorship bias.

El Gaussian HMM utiliza `hmmlearn`, añadido como dependencia necesaria para
implementar el modelo solicitado. Requiere un `random_state` explícito; la suite
debe instalar las dependencias del proyecto (`python -m pip install -e ".[dev]"`).

## Reporting y tracking de experimentos

`reporting.build_research_report` recibe resultados de backtest, métricas ya
calculadas y una comparación de benchmark; incorpora configuración,
parámetros, equity curve, drawdown, trades y warnings. Renderiza JSON, CSV o
HTML escapado con gráficos SVG. Para escribir, indica explícitamente el destino
con `write_json_report`, `write_csv_report` o `write_html_report`; no se abre
ningún navegador ni se escriben archivos al importar.

`experiments.ExperimentRegistry` registra metadata JSON con timestamp UTC,
estrategia/parametría, fingerprint SHA-256 estable de los datos, símbolos,
fechas, versión Git opcional, métricas, outputs y warnings. La persistencia es
atómica y exclusiva: un ID existente nunca se sobrescribe. Los campos con
nombres típicos de secretos se guardan como `[REDACTED]`. El `.gitignore`
excluye `reports/generated/`, `experiments/runs/` y archivos de reporte
generados. No se incluye MLflow ni almacenamiento externo.

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
