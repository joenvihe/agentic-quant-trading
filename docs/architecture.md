# Arquitectura inicial

## Principios

- Mantener los componentes de investigación desacoplados y con interfaces
  explícitas.
- Separar configuración de la lógica cuantitativa y leerla desde un único
  punto de entrada.
- Favorecer cálculos reproducibles y deterministas; añadir dependencias solo
  cuando una necesidad concreta lo justifique.
- No realizar acciones externas implícitas al importar módulos.

## Módulos

- `data/`: contrato OHLCV, validación, almacenamiento CSV y adaptadores de
  proveedores externos. El proveedor implementa `MarketDataProvider`; el
  motor no depende de Yahoo Finance directamente.
- `scripts/`: comandos de usuario. `python -m scripts.download_market_data
  TICKER` y `python -m scripts.research_asset TICKER` son entry points CLI.
- `application/services/`: orquesta el flujo de investigación y arma el
  reporte, sin implementar cálculos cuantitativos.
- `features/`: Quant Feature Engine calcula indicadores exclusivamente sobre
  el contrato OHLCV normalizado de `data/`.
- `factors/`: Momentum Engine rankea activos usando retornos y percentiles;
  produce factores/rankings, no señales ni operaciones.
- `regime/`: Market Regime Engine clasifica dirección, fuerza, volatilidad y
  confirmación con reglas deterministas y thresholds configurables. El
  complemento `GaussianHMMRegime` detecta estados estadísticos con seed
  obligatorio y `compare_regimes` compara direcciones sin reemplazar el baseline.
- `signals/`: contratos de señales y generadores que consumen resultados de
  features existentes. `MovingAverageCrossSignal` lee SMA disponibles, opera
  en modo long-only y no descarga datos.
- `strategies/`: contratos y estrategias deterministas que transforman
  señales/factores y régimen en `TargetPosition`. Incluye el mapeo
  `MovingAverageStrategy`, la estrategia long-only `MomentumRegimeStrategy` y
  un `StrategyRegistry` de registro explícito.
- `risk/`: motor puro de aprobación y sizing de exposición; aplica límites por
  activo/cartera, volatility targeting opcional y circuit breaker de drawdown.
- `backtest/`: simulación diaria, long-only y de un activo. Recibe posiciones
  objetivo y ejecuta la información de cierre en la apertura del bar siguiente,
  contabilizando comisión y slippage; no realiza trading real.
- `execution/`: protocolo de broker, órdenes market, posiciones y estado de
  cuenta inmutables, y `PaperBroker` en memoria. Solo ejecuta con el precio
  explícito recibido del caller, registra comisión/slippage y rechaza fondos
  insuficientes o ventas cortas. No conecta servicios, recibe credenciales,
  realiza networking, genera señales ni elige qué comprar.
  Las órdenes market se resuelven sincrónicamente; `CANCELLED` forma parte del
  contrato común, pero no hay órdenes pendientes que cancelar en este broker.
- `portfolio/`: asignación equal-weight y optimización long-only de Sharpe
  máximo sobre series de retornos normalizados; no descarga datos ni ejecuta
  órdenes. El optimizador usa SciPy SLSQP con restricciones de caja y suma.
- `fundamental/`: contratos point-in-time para providers y snapshots, cálculos
  de ROC, earnings yield y P/E, y ranking Magic Formula; no genera órdenes.
- `universe/`: providers de universos explícitos, normalización/deduplicación
  de símbolos y filtros deterministas de datos, precio, historial y
  capitalización disponible.
- `reporting/`: proyecciones tabulares y generación explícita de informes JSON,
  CSV y HTML escapado desde resultados y métricas ya calculados; charts SVG
  locales, sin navegador ni efectos durante imports.
- `experiments/`: huellas SHA-256 canónicas y registro JSON de experimentos con
  redacción de claves sensibles y publicación atómica que no sobrescribe runs.
- `sentiment/`: provider de noticias inyectable, fake local, VADER y agregación
  temporal alineada a timestamps de features. La agregación solo considera
  artículos publicados hasta el timestamp de cada observación; sentimiento es
  una feature, no una señal ni una orden.
- `models/`: construcción de datasets y targets de dirección futura con
  timestamps separados, split temporal con purga de etiquetas que alcanzan el
  test, escalado ajustado sobre train, clasificador logístico baseline,
  XGBoost y métricas de clasificación. Las predicciones son `MLSignal`, nunca
  órdenes; accuracy no representa rentabilidad.
- `evaluation/`: métricas de rendimiento, benchmark Buy and Hold y comparación
  entre resultados simulados; incluye splits temporales, validación walk-forward
  y resumen de robustez.
- `agents/research/`: orquestador determinista de requests estructurados sobre
  un allowlist fijo de servicios/tools; registra llamadas, evidencia,
  warnings y trace ID. Un planner sin LLM propone únicamente el flujo
  permitido; la política valida el plan antes de ejecutar. Dry-run muestra el
  plan sin leer datos ni escribir archivos. No ejecuta código de requests, no
  modifica estrategias ni utiliza PaperBroker.
- `app/`: futuros puntos de entrada e integración.
- `config/`: ajustes tipados y configuración explícita de logging.
- `tests/`: pruebas automatizadas con pytest.
- `docs/`: documentación técnica.

Los límites cuantitativos son explícitos: Feature != Factor != Signal !=
Strategy != Order. Momentum permanece como factor/ranking. Una estrategia solo
devuelve una posición objetivo; no crea órdenes ni realiza ejecución. Las
dependencias fluyen hacia componentes de dominio más pequeños, evitando ciclos.

## Market Data Engine v0.1

El vertical slice actual descarga barras diarias OHLCV de Yahoo Finance,
normaliza los timestamps a UTC, valida orden, duplicados, valores ausentes,
precios y coherencia OHLC, persiste en `data/market_data/<TICKER>.csv`, vuelve
a validar al leer y presenta un resumen. `AQT_DATA_DIR` cambia el directorio
raíz de persistencia.

Yahoo Finance es una fuente de terceros sin garantía de disponibilidad; el
comando no sustituye datos corregidos ni informa éxito si la descarga o
validación falla. Las pruebas usan datos sintéticos y no necesitan Internet.

Estos motores no conectan brokers reales ni gestionan dinero real. `PaperBroker`
es una simulación local en memoria que puede ejecutar órdenes paper únicamente
con precios explícitos proporcionados por el caller. El agente de investigación
es determinista y no utiliza LLM ni LangGraph.

## Signals + Strategies — Fase 1

`signals.MovingAverageCrossSignal` recibe un `FeatureSeries` existente, evalúa
la última fila con períodos SMA configurables entre los que ofrece el Feature
Engine (20, 50, 100 y 200), y emite `LONG` si SMA rápida > SMA lenta; en otro
caso emite `FLAT`. Si falta alguno de los valores por historial insuficiente,
emite `FLAT` con metadatos que explican esa ausencia. Señales tienen timestamp
timezone-aware, dirección, strength acotada y source.

`strategies.MovingAverageStrategy` convierte `LONG` en peso objetivo 1 y
`FLAT` en peso 0. `MomentumRegimeStrategy` exige `absolute_momentum` positivo y
un régimen permitido; la allowlist predeterminada es `BULL_STRONG` y
`BULL_VOLATILE`, validada contra los seis estados emitidos por Market Regime
Engine. Ambas devuelven `TargetPosition` (peso entre -1 y 1) y razón
descriptiva. `StrategyRegistry` solo registra instancias explícitas y rechaza
nombres repetidos.

No hay señales SHORT generadas por esta primera regla, órdenes ni brokers.

## Backtest + Performance Metrics — Fase 2

`backtest.run_backtest` recibe barras OHLCV ya normalizadas y `TargetPosition`
con timestamps alineados a esas barras. La posición calculada con información
del cierre `t` solo se ejecuta a la apertura de `t+1`. El tamaño se calcula
con equity y cierre conocidos en `t`; el precio de ejecución incorpora slippage
adverso y la comisión se descuenta del efectivo. Las barras no se liquidan
forzosamente al final. No se permite cash negativo por compras, exposición
fuera de [0, 1], margen ni posiciones cortas. La última posición indicada no
tiene efecto si no hay bar posterior.

La primera versión opera un solo activo en barras diarias y no deriva
posiciones por sí misma: el caller entrega posiciones objetivo que una
estrategia produjo usando información disponible en sus timestamps.
`evaluation.buy_and_hold_benchmark` y el motor de estrategia comparten el
modelo de ejecución al siguiente bar. Las métricas se encuentran documentadas
en `docs/performance_metrics.md`; ratios sin denominador válido se representan
como `None`.

Esto es una simulación de investigación. No hay órdenes reales ni conexión a
broker.

## Walk-Forward Validation + Risk — Fase 3

`evaluation.generate_time_splits` crea ventanas expanding o rolling en orden
cronológico desde barras diarias; exige timestamps UTC-aware, únicos y
ordenados, y garantiza `train_end < test_start`. No se barajan observaciones.
`evaluation.run_walk_forward` evalúa candidatos explícitos solo con la
ventana train, maximiza por defecto (o minimiza si se configura) una métrica
configurable y ejecuta el candidato elegido con datos exclusivamente de la
ventana test.
El callback recibe una sola ventana cada vez y debe construir señales y
posiciones usando solo sus datos. Los resultados incluyen ventana, candidatos,
selección, métricas in-sample/out-of-sample y warnings. Si ninguna métrica
train es válida, no se selecciona una configuración y test no se evalúa.

El test window no incluye datos de train para warm-up. Por ello, estrategias
que necesiten contexto deben proporcionar historial suficiente dentro de cada
ventana test o el callback debe gestionar warm-up sin usar observaciones test
futuras.

`risk.evaluate_risk` es una función pura: recibe la exposición solicitada,
exposición actual, límites, volatilidad realizada anualizada opcional y
drawdown actual como fracción positiva. Puede reducir peso por activo y
exposición agregada, aplicar volatility targeting o bloquear la exposición al
alcanzar el drawdown máximo. Devuelve un `RiskDecision` con peso aprobado,
estado y reason codes. No elige estrategias, modifica precios ni ejecuta
órdenes. Riesgo no está conectado automáticamente al backtest en esta fase.

Walk-forward y riesgo son herramientas de investigación; no ejecutan órdenes.

## Portfolio Optimization — Fase 4

`portfolio.EqualWeightAllocator` asigna pesos iguales sin dependencias
numéricas y verifica límites y suma totalmente invertida.
`portfolio.MaximumSharpeOptimizer` recibe símbolos explícitos y series
alineadas de retornos ya normalizados; no recibe precios ni descarga datos.
Estima medias aritméticas y covarianza muestral, anualiza ambas con
`periods_per_year` y maximiza el Sharpe respecto a `risk_free_rate`, respetando
long-only, límites por activo y suma de pesos igual a uno.

SciPy no estaba presente en las dependencias del proyecto ni en el entorno
Python comprobado. Se declara `scipy>=1.11` porque el problema de Sharpe máximo
es una optimización fraccional no lineal con restricciones y requiere un solver
numérico confiable; SLSQP se invoca con punto inicial y tolerancias fijos para
resultados reproducibles. Si el solver falla o los datos implican volatilidad
cero, se devuelve `AllocationResult(success=False)`; nunca se sustituye el
resultado por equal-weight.

## HMM Regime, Fundamentals y Universe Selection — Fase 5

`regime.GaussianHMMRegime` no altera el clasificador determinista existente.
Calcula log returns y rango diario `(high - low) / close`, exige un
`random_state`, y permite configurar el número de estados (dos por defecto).
Los IDs internos no tienen interpretación direccional: cada estado se reporta
con `hidden_state_id`, etiqueta estadística y estadísticas de retorno medio,
rango normalizado medio, volatilidad de retornos y observaciones. Las etiquetas
usan drift observado y clasifican alta volatilidad respecto de la mediana de
los estados con muestra suficiente; con menos de dos observaciones un estado se
marca insuficiente por defecto. `compare_regimes` compara dirección determinista
con drift HMM, y deja el acuerdo indefinido cuando la muestra no permite
etiquetar o la clasificación determinista no aporta dirección.
El resultado se limita al último timestamp del histórico recibido; el ajuste y
las estadísticas usan el histórico hasta ese corte, no observaciones
posteriores. Para una prueba histórica en una fecha pasada, el caller debe
limitar `MarketData` a esa fecha antes de ajustar el modelo.

`fundamental.FundamentalDataProvider` exige un corte temporal timezone-aware;
`fetch_fundamental_snapshot` valida que el provider no retorne datos posteriores
al corte. `FundamentalSnapshot.as_of` representa la fecha en que la información
estuvo disponible públicamente, no necesariamente el cierre del período fiscal.
ROC se calcula como EBIT / (capital de trabajo neto + activos fijos
netos), earnings yield como EBIT / enterprise value y P/E como market cap /
net income. Los campos faltantes y denominadores no positivos producen `None`,
nunca cero. El ranking combinado recibe un corte común, rechaza datos
posteriores, y promedia los rangos disponibles de ROC y earnings yield. El
resultado no representa señales u órdenes.

`universe.StaticUniverseProvider` normaliza tickers y elimina duplicados
preservando el orden. `universe.select_universe` combina sus candidatos con un
provider inyectado de metadatos y un corte `as_of` timezone-aware; los metadatos
posteriores al corte se rechazan. Aplica filtros configurables de precio,
historial, datos faltantes y capitalización. Una capitalización ausente no se
trata como cero ni causa rechazo por capitalización; valores presentes no
válidos se rechazan. Cada rechazo conserva un reason code explícito. La
composición de un universo estático point-in-time depende del caller; una lista
actual no debe reutilizarse como universo histórico por survivorship bias.

`hmmlearn` no estaba declarado ni instalado en el entorno inspeccionado. Se
declara como dependencia porque provee el Gaussian HMM solicitado; el HMM usa
semilla explícita y covarianza diagonal. Los tres componentes son herramientas
de análisis offline y no descargan datos por sí mismos.

## Reporting + Experiment Tracking — Fase 6

`reporting.build_research_report` agrega `BacktestResult`, `PerformanceMetrics`,
comparación con benchmark, configuración, parámetros, símbolos, warnings y
archivos generados. No vuelve a ejecutar estrategias ni recalcula métricas. La
curva de drawdown se deriva de la equity curve solo para presentación. Los
renderers producen JSON estable, CSV tabular y HTML autocontenido con SVG y
contenido de usuario escapado. Los writers requieren una ruta explícita,
crean directorios solo al invocarse y nunca abren un navegador.

`experiments.data_fingerprint` calcula SHA-256 sobre JSON canónico del input;
`ExperimentRegistry.register` registra timestamp UTC, estrategia, parámetros,
huella de datos, símbolos, período, versión Git cuando está disponible,
métricas, archivos y warnings. `save_experiment` escribe metadata JSON a un
temporal en el mismo directorio y publica mediante hard-link atómico con
creación exclusiva; IDs existentes no se sobrescriben. Claves de metadata con
nombres de credenciales/secretos se sustituyen por `[REDACTED]`. El registro es
local y no sustituye un proveedor de almacenamiento distribuido.

## Sentiment + modelos supervisados — Fase 7

`sentiment.NewsProvider` es un contrato inyectable; `FakeNewsProvider` permite
pruebas y fixtures sin Internet. `VaderSentimentScorer` carga VADER solo al
instanciarse. `align_sentiment` calcula para cada timestamp un promedio
compuesto, cantidad de noticias, dispersión y cobertura temporal usando una
ventana trailing inclusiva; `merge_sentiment_features` puede añadir las tres
columnas numéricas a `FeatureSeries` para construir datasets. Las noticias
futuras se excluyen y una ventana sin noticias produce score/dispersión
`None`, no cero.

`models.build_ml_dataset` reutiliza `FeatureSeries` causal y crea el target
binario de retorno forward con horizonte configurable. Cada muestra distingue
`feature_timestamp` de `target_timestamp`; los últimos bars sin futuro se
omiten. `temporal_train_test_split` no baraja, reserva el tramo cronológico
final y purga del entrenamiento muestras cuyo target timestamp alcanza el
inicio del test. `BaselineClassifier` ajusta su scaler solo sobre train y usa
un modelo logístico reproducible con `random_state` obligatorio.
`XGBoostClassifier` también exige semilla, usa un hilo y árboles `hist`; no
estandariza variables porque los árboles no lo requieren. Ambas APIs devuelven
`MLSignal` con clase/probabilidad y timestamp de features, no órdenes.
`evaluate_classifier` devuelve accuracy, precision, recall, F1, ROC-AUC cuando
ambas clases están presentes y matriz de confusión. Estas métricas de
clasificación no equivalen a rentabilidad ni reemplazan un backtest OOS.

VADER y XGBoost no estaban instalados en el entorno Python inspeccionado y se
declaran como dependencias del proyecto. No se conecta ninguna API de noticias;
el caller debe suministrar items y garantizar su procedencia y disponibilidad
histórica.

## Momentum Engine v0.1

`python -m scripts.rank_momentum SPY QQQ IWM DIA` recupera datos a través de
Market Data Engine, calcula features y rankea momentum de 1/3/6/12 meses. El
momentum absoluto significa retorno 12M mayor que cero; el relativo es el
percentil de cada horizonte dentro del universo. El score compuesto es el
promedio ponderado de esos percentiles y el percentil final compara scores.
Los pesos iguales por defecto se configuran con `AQT_MOMENTUM_WEIGHT_*`.
El resultado es un factor de ranking, no una señal, un trade ni una
recomendación de compra/venta.

## Market Regime Engine v0.1

`python -m scripts.detect_regime TICKER` descarga OHLCV mediante Data Engine,
calcula exclusivamente las features existentes y devuelve `regime`, `metrics`,
`evidence` y `reason_codes`. El baseline es determinista e interpretable; no
usa machine learning, clustering, HMM ni LLM. Clasifica dirección comparando
SMA50/SMA200; fuerza usando retornos 6M/12M; volatilidad con volatilidad
realizada anualizada y ATR14/SMA20; confirmación con retornos, SMA20/SMA50 y
un proxy de precio derivado de features. La precedencia es CHAOTIC, BEAR,
BULL_VOLATILE, BULL_STRONG, RANGE y, para el resto o historial insuficiente,
TRANSITION. Thresholds, valores iniciales, criterios y variables de entorno
están documentados en el README y en `config/regime.py`. Es una clasificación
descriptiva y no una recomendación de mercado.

## Quant Research vertical slice

`python -m scripts.research_asset TICKER` orquesta los módulos existentes en
orden: Market Data y validación, features, factor de momentum, régimen y
reporte. Los indicadores y clasificaciones se reutilizan; el CLI solo presenta
el resultado. Los campos sin datos suficientes se reportan como `N/A`, con
advertencias de historial insuficiente. Score y percentil relativos aparecen
como `N/A` para un solo ticker porque no existe universo comparativo.

## Quant Research Agent — Fase 10

`agents.research.ResearchAgent` recibe símbolos, estrategias, fechas, costos y
rutas mediante `ResearchAgentRequest`; no interpreta texto libre como código o
selección de herramientas. `DeterministicResearchPlanner` propone un flujo
fijo de investigación y `policy.authorize_plan` comprueba cada llamada contra
un allowlist de estrategias y herramientas antes de cualquier descarga o
escritura. Una llamada `strategy_research` reutiliza el servicio existente, que
compone datos, estrategia, riesgo, equal-weight, backtest, evaluación y reportes.
Si se solicitan varias estrategias, el agente usa la herramienta tipada de
comparación; genera un resumen a partir de métricas y evidencia devueltas por
estos componentes.

Cada ejecución registra un `trace_id`, llamadas, evidencia, warnings y errores;
`ResearchAgentState.to_dict()` produce datos JSON-safe. El modo `dry_run`
valida y muestra el plan sin invocar providers ni escribir archivos. No se usa
LLM o LangGraph: el workflow es determinista y acotado, de modo que un framework
de grafos no aporta capacidades necesarias. El agente no ejecuta código de
requests, exige rutas configuradas absolutas sin traversal ni enlaces
simbólicos, no modifica estrategias, no accede a credenciales, no conecta
PaperBroker y no afirma rentabilidad futura.
