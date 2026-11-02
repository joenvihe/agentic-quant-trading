# Auditoría de arquitectura actual (AS-IS)

**Repositorio:** `agentic-quant-trading`
**Fecha de revisión:** 2026-11-02
**Alcance:** inspección estática del árbol actual, contratos públicos, imports,
flujo de llamadas, documentación y pruebas existentes. No se modificó código
productivo ni se eliminaron archivos.

## 1. Resumen ejecutivo

El repositorio contiene una plataforma educativa de investigación cuantitativa
con contratos separados para datos, features, factores, señales, posiciones,
órdenes simuladas, evaluación y reporting. Hay dos caminos de investigación:

1. El flujo single-asset de `application.services.research` genera un informe
   de mercado, features, momentum y régimen.
2. El flujo multi-asset de `application.services.strategy_research` genera
   posiciones y ejecuta sleeves de backtest por activo; calcula métricas,
   benchmark, reportes y registro del experimento.

Además existen motores autónomos de HMM, fundamentales, sentiment/ML,
walk-forward, optimización de portfolio y PaperBroker. Su presencia en el
repositorio no significa que estén integrados al flujo multi-asset principal.
El agente usa un planner determinista y un allowlist; no usa LLM ni PaperBroker.

**Estado global: PARTIAL / no certificado.** `docs/MASTER_PLAN.md` marca las
fases de la 1 a la 10 como `PARTIAL` hasta que corra la suite completa. Se
intentó ejecutar la suite y el resultado real se consigna al final. No se
infiere éxito de la existencia de módulos o tests.

## 2. Arquitectura y flujo actual

### 2.1 Límites de responsabilidad

```text
Provider de mercado
  → Market Data Engine / validación / CSV
  → Quant Feature Engine
  → Momentum factor y/o Market Regime determinista
  → señal (Moving Average) o estrategia (Momentum + Regime)
  → Risk Engine
  → Equal Weight Allocation
  → backtest diario long-only por activo
  → agregación de sleeves / métricas / benchmark
  → JSON, CSV, HTML / Experiment Registry
```

`execution.PaperBroker` es una simulación independiente, no una etapa de este
pipeline. HMM, fundamentales, universe screening genérico, sentiment/ML y
walk-forward también son capacidades aisladas que no se llaman desde el flujo
principal. El orden de la documentación que termina en `Execution` es un mapa
conceptual; no representa que el pipeline envíe órdenes.

Como flujo conceptual del dominio, la cadena solicitada es:

```text
Data → Features → Factors → Regime → Signals → Strategy → Risk → Portfolio
     → Backtest → Evaluation → Reporting
```

La implementación actual ramifica en lugar de ser una cadena única: la
estrategia `moving_average` consume una señal desde features (aunque el servicio
también calcula ranking/regime por timestamp, esos resultados no determinan esa
estrategia); `momentum_regime` consume factor y régimen directamente y no pasa
por `Signal`. Paper execution tampoco forma parte de este flujo de research.

### 2.2 Flujo de investigación single-asset

`scripts/research_asset.py::main` configura settings/logging, construye
`YahooFinanceProvider` y llama a
`application.services.research.generate_research_report`. El servicio llama
a `run_market_data_engine`, calcula las features, calcula momentum cuando hay
historial suficiente, evalúa el régimen determinista y devuelve un
`ResearchReport`; `render_research_report` convierte el resultado en texto.
No hace backtest, sizing de riesgo ni ejecución.

### 2.3 Flujo de investigación multi-asset

`scripts/run_strategy_research.py::main` valida argumentos e invoca
`run_strategy_research` con un `MarketDataProvider` inyectable. El servicio:

1. normaliza/deduplica símbolos, selecciona una estrategia permitida y llama
   al Market Data Engine por símbolo;
2. conserva historia para warm-up, filtra las barras del periodo solicitado,
   calcula `FeatureSeries` y alinea fechas comunes;
3. en cada timestamp usa prefijos históricos, calcula momentum cross-sectional
   cuando hay historial suficiente y detecta el régimen determinista;
4. genera `TargetPosition` por moving average o momentum/regime y pasa los
   pesos por `evaluate_risk`;
5. crea una asignación equal-weight y ejecuta un backtest single-asset por
   símbolo con sleeves de capital iguales;
6. suma las curvas de equity de los sleeves, compara contra Buy and Hold,
   escribe JSON/CSV/HTML y registra el experimento.

El parámetro `MaximumSharpeOptimizer` no se usa por este flujo. Tampoco se
llaman HMM, fundamental, sentiment, modelos ML o walk-forward. El riesgo y el
drawdown se evalúan por activo; los resultados multi-asset son una agregación
de sleeves sobre timestamps comunes, no un motor de cartera consolidado.

### 2.4 Flujo del agente

`agents.research.ResearchAgent` valida un request estructurado, obtiene un plan
de `ResearchPlanner`, y `authorize_plan` lo compara con el plan fijo de
`agents.research.policy`. El allowlist contiene research, comparación y
reporting. `dry_run` registra las llamadas planeadas sin leer datos o escribir
reportes. En ejecución, el agente llama directamente al servicio
multi-asset, a los adapters de comparación y reporting, y forma evidencia y
resumen a partir de sus resultados. No ejecuta código de requests, no llama a
PaperBroker y no usa LangGraph ni un LLM.

## 3. Mapa AS-IS por módulo

La columna “estado” distingue código observado de integración: **Implementado
estáticamente** no equivale a probado en runtime. **Parcial** indica una
capacidad que existe con alcance limitado, no integrada o pendiente de
aceptación según el Master Plan.

| Módulo | Responsabilidad, contratos y APIs principales | Interfaces / dependencias y llamadas | Tests existentes | Estado observado |
|---|---|---|---|---|
| `data/` | Contratos `MarketBar`, `MarketData`, `MarketDataProvider`; errores `MarketDataError`, `MarketDataDownloadError`, `MarketDataValidationError`; `normalize_ticker`, `normalize_market_data`. `data.engine::run_market_data_engine` orquesta proveedor → normalización → persistencia → relectura; `data.storage::{market_data_path,save_market_data,load_market_data}` gestiona CSV; `YahooFinanceProvider` adapta yfinance. | Las capas superiores dependen de `MarketData` y de `MarketDataProvider`; solo el provider Yahoo importa yfinance. El engine depende de `data.market_data` y `data.storage`. Escrituras/descargas ocurren en llamadas explícitas, no por una feature. | `tests/test_market_data.py`, `tests/test_import_characterization.py`; fake provider para el engine. | Implementado como fuente normalizada; pruebas no certificadas en esta ejecución. Normalización valida el orden que recibe, no ordena silenciosamente barras. |
| `features/` | `FeatureRow`, `FeatureSeries`, `FeatureError`, `FEATURE_NAMES`, `calculate_features`. Calcula SMA/EMA, RSI, retornos 1/3/6/12M, ATR, realized volatility, Bollinger, volumen relativo y estructura de 52 semanas; historia insuficiente queda `None`. | Consume únicamente `data.MarketData`; no accede a providers. Consumido por factors, régimen, signals, research services, ML dataset y scripts. | `tests/test_features.py`, indirectamente `test_signals.py`, `test_regime.py`, `test_models.py`. | Implementado de forma determinista; separado del Market Data Engine. |
| `factors/` | `MomentumRank`, `MomentumRankingError`, `rank_momentum`; percentiles relativos por horizonte y score ponderado, junto a momentum absoluto 12M. | Consume `FeatureSeries` y `config.MomentumWeights`; lo usan servicios single/multi-asset, estrategias, aplicación y CLI `rank_momentum`. No genera señales u órdenes. | `tests/test_momentum.py`, `tests/test_strategies.py`, `tests/test_research_asset.py`, `tests/test_strategy_research.py`. | Factor implementado; ranking cross-sectional de un solo activo tiene alcance limitado. |
| `fundamental/` | `FundamentalSnapshot`, `FundamentalMetrics`, `FundamentalDataProvider`, `fetch_fundamental_snapshot`, `calculate_fundamental_metrics`, `calculate_magic_formula_metrics`, `rank_fundamentals` y `FundamentalRank`; métricas ROC, earnings yield, P/E y ranking combinado. | Provider es un `Protocol` y recibe `as_of`; no se halló un provider externo concreto. Consume datos fundamentales inyectados; no genera órdenes ni está conectado al pipeline/CLI. | `tests/test_fundamental.py`. | Cálculo/ranking implementado; suministro real de datos no implementado y no integrado. |
| `sentiment/` | `NewsItem`, `NewsProvider`, `FakeNewsProvider`, `VaderSentimentScorer`, `SentimentFeature`, `aggregate_sentiment`, `align_sentiment`, `merge_sentiment_features`. Incluye scoring agregado, conteo, dispersión y alineamiento point-in-time. | Provider inyectado; imports VADER en el scorer. Alinea noticias a `FeatureSeries`; no se llama desde pipeline, strategy, backtest ni agente. | `tests/test_sentiment.py`, `tests/test_import_characterization.py`. | Feature implementada para noticias aportadas por caller; no existe fuente real ni integración al pipeline. |
| `regime/` | `RegimeAssessment`, `detect_regime` (baseline por features/thresholds); `GaussianHMMRegime`, `HMMRegimeResult`, `HMMStateStatistics`; `compare_regimes`, `RegimeComparison`. | Baseline consume `FeatureSeries` y `RegimeThresholds`; HMM consume barras normalizadas y `hmmlearn`; comparación contrasta labels. El pipeline integrado llama solo `detect_regime`, no HMM. | `tests/test_regime.py`, `tests/test_regime_hmm.py`. | Baseline integrado; HMM y comparación implementados aparte, ambos no integrados al pipeline. |
| `signals/` | `SignalDirection`, `Signal`, `SignalGenerator`, `MovingAverageCrossSignal`; emite LONG/FLAT leyendo SMA configurables disponibles en features. | Depende de `FeatureSeries`; el servicio multi-asset usa el generador para moving_average. No descarga datos ni genera órdenes. | `tests/test_signals.py`, `tests/test_import_characterization.py`. | Señal MA implementada e integrada en su estrategia; no hay una biblioteca más amplia de señales. |
| `strategies/` | `TargetPosition`, `Strategy`, `MovingAverageStrategy`, `MomentumRegimeInput`, `MomentumRegimeStrategy`, `StrategyRegistry`. Transforma una señal o factor+regime a una posición objetivo. | La estrategia MA consume `Signal`; MomentumRegime consume `MomentumRank` y `RegimeAssessment`; backtest consume `TargetPosition`. Registry es explícito, sin imports dinámicos. | `tests/test_strategies.py`, `tests/test_backtest.py`, `tests/test_strategy_research.py`. | Dos estrategias long-only implementadas; no crean órdenes. |
| `risk/` | `RiskLimits`, `RiskDecision`, `evaluate_risk`, `apply_weight_and_exposure_limits`, sizing, volatility targeting y `drawdown_breached`. | Consume peso solicitado, exposición actual, volatilidad y drawdown proporcionados por caller. Lo llama el servicio multi-asset; no ejecuta ni altera mercado. | `tests/test_risk.py`, `tests/test_strategy_research.py`, `tests/test_application_tools.py`. | Risk Engine de decisión implementado; integración multi-asset es por activo/sleeves y sin curva consolidada de drawdown. |
| `portfolio/` | `PortfolioConstraints`, `AllocationResult`, `EqualWeightAllocator`, `validate_symbols`, `estimate_covariance`, `MaximumSharpeOptimizer`. Optimización SLSQP mediante SciPy; fallo devuelve resultado explícito, sin fallback silencioso. | Recibe series de returns normalizadas del caller. `strategy_research` usa `EqualWeightAllocator`; el adapter de portfolio llama a `MaximumSharpeOptimizer`. El optimizer no toma precios ni se usa en el backtest integrado. | `tests/test_portfolio.py`, `tests/test_application_tools.py`, `tests/test_strategy_research.py`. | Equal weight integrado; optimizador implementado standalone; no hay allocator optimizer → backtest en el pipeline principal. |
| `backtest/` | `BacktestConfig`, `Trade`, `EquityPoint`, `BacktestResult`, `calculate_execution_cost`, `run_backtest`; valida datos/targets y simula single-asset diario, long-only, costes y ejecución del target de cierre `t` en apertura `t+1`. | Consume `MarketData`, `TargetPosition`; usa backtest costs. Consumido por benchmark/evaluation, aplicación y servicio multi-asset. | `tests/test_backtest.py`, `tests/test_application_tools.py`, `tests/test_strategy_research.py`. | Motor base implementado y aislado; alcance limitado a un activo por corrida. |
| `evaluation/` | `PerformanceMetrics`, `calculate_metrics`, `buy_and_hold_benchmark`, `PerformanceComparison`, `compare_performance`, `TimeWindow`, `generate_time_splits`, `slice_market_data`, `run_walk_forward`, `summarize_robustness`. | Métricas reciben `BacktestResult`; benchmark reutiliza backtest; walk-forward usa callback `BacktestEvaluator` y particiones cronológicas. Comparación/metricas se usan en pipeline; walk-forward no. | `tests/test_backtest.py`, `tests/test_walk_forward.py`, `tests/test_application_tools.py`, `tests/test_strategy_research.py`. | Métricas y benchmark integrados; split/walk-forward implementados, aún no conectados a estrategia CLI/agente y callback debe seguir reglas causales. |
| `execution/` | `Order`, `OrderSide`, `OrderType`, `OrderStatus`, `OrderExecution`, `Position`, `AccountState`, `Broker`, `PaperBroker`; simulación in-memory long-only de market orders, comisión y slippage. | Precio recibido explícitamente del caller; reutiliza costes de backtest. No hay provider de precios, red ni consumidor en `application/tools`, service o agent. | `tests/test_execution.py`, `tests/test_import_characterization.py`. | PaperBroker implementado aislado. Broker real/live explícitamente fuera de alcance. |
| `experiments/` | `ExperimentRecord`, `data_fingerprint`, `sanitize_metadata`, `ExperimentRegistry`, `save_experiment`, `load_experiment`; metadata JSON, fingerprint y almacenamiento exclusivo/atómico descrito en tests. | Usa `pathlib`, `json`, hashing estándar y Git best-effort. Llamado al final de `run_strategy_research`; no forma parte del dominio de trading. | `tests/test_experiments.py`, `tests/test_strategy_research.py`. | Tracking local implementado; dependencia de Git es opcional; persistencia a validar runtime. |
| `reporting/` | `ResearchReport`, `build_research_report`, tablas `metrics_table/equity_rows/trade_rows/report_tables`, render/write JSON/CSV/HTML y `render_line_chart_svg`. | Consume resultados/metricas/comparison ya calculados; writers usan rutas explícitas. Usado por servicio multi-asset y tool de reporting. | `tests/test_reporting.py`, `tests/test_application_tools.py`, `tests/test_strategy_research.py`. | Formatos implementados; no recalcula estrategia; generación es explícita. |
| `application/` | `services.research::{ResearchReport,generate_research_report,render_research_report}`; `services.strategy_research::{StrategyResearchResult,run_strategy_research}`. Adapters con `ToolResponse`, `resolve_trace_id`, `to_serializable` y requests/entry points de research, backtest, comparison, risk, portfolio y reporting. | Services orquestan domain APIs; adapters envuelven services/engines. El CLI y agente usan services/tools. Excepciones se traducen en fronteras de aplicación. | `tests/test_research_asset.py`, `tests/test_strategy_research.py`, `tests/test_application_tools.py`, `tests/test_import_characterization.py`. | CLI/services y adapters existen; faltan API/UI general y pipeline portfolio consolidado. |
| `agents/` | `ResearchAgentRequest`, `ResearchPlanner`, `DeterministicResearchPlanner`, `ResearchAgent`, `run_research_agent`; `AgentToolCall`, `ResearchAgentState`; `authorize_plan`, `expected_plan`; `render_research_summary`. | Consume servicio strategy research y tools de comparación/reporting; allowlist fijo `strategy_research`, `comparison`, `reporting`. Sin LLM, broker, ejecución arbitraria ni framework de agentes. | `tests/test_research_agent.py`, `tests/test_import_characterization.py`. | Agente determinista implementado; no es un agente LLM, característica deliberadamente ausente. |
| `scripts/` | Entry points `download_market_data.main`, `analyze_features.main`, `rank_momentum.main`, `detect_regime.main`, `research_asset.main`, `run_strategy_research.main`; parseo/formatting local a CLI. | Scripts construyen provider Yahoo para uso explícito o aceptan provider inyectado en tests; delegan a servicios/domain. | `tests/test_market_data.py`, `test_features.py`, `test_momentum.py`, `test_regime.py`, `test_research_asset.py`, `test_strategy_research.py`, import characterization. | CLIs presentes; los scripts no constituyen una API general. |
| `config/` | `Settings`, `MomentumWeights`, `RegimeThresholds`, `configure_logging`. | Settings/thresholds son leídos por services y scripts; logging se configura explícitamente en CLI. Valores de momentum/régimen pueden venir del entorno. | `tests/test_smoke.py`, `tests/test_momentum.py`, `tests/test_regime.py`, import characterization. | Configuración implementada; policy de logging uniforme entre todas las fronteras sigue parcial según Master Plan. |
| `models/` | `DirectionTarget`, `generate_direction_targets`, `DatasetSample`, `MLDataset`, `DatasetSplit`, `build_ml_dataset`, `temporal_train_test_split`, `FittedStandardizer`, `fit_standardizer`, `BaselineClassifier`, `XGBoostClassifier`, `MLSignal`, `evaluate_classifier`. | Consume MarketData y FeatureSeries; scaler se ajusta al train entregado; targets llevan timestamp de feature/target y split purga targets solapados. No importado por estrategia/pipeline/agent. | `tests/test_models.py`, `tests/test_import_characterization.py`. | Dataset/modelos implementados como API standalone; no estrategia ML ni conversión de predicción a órdenes. |
| `universe/` | `UniverseProvider`, `UniverseDataProvider`, `StaticUniverseProvider`, `UniverseAssetData`, `UniverseFilters`, `select_universe`, `UniverseRejection`, `UniverseSelectionResult`. | Universe estático y data provider inyectado; service reporta aceptaciones/rechazos. El pipeline strategy-research usa universo estático y un adaptador privado de datos ya cargados; no aplica filtros de producción más allá de historial mínimo 1. | `tests/test_universe.py`, `tests/test_strategy_research.py`. | Screening implementado; sin fuente externa de universo; integración de research actualmente trivial/limitada. |
| `app/` | Solo `app/__init__.py`; no hay API web, UI o entrypoint de aplicación. | Sin dependencias o callers detectados. `application/` es el paquete funcional distinto. | Ninguna prueba dedicada. | Placeholder; la capa general `app/` no implementada (también lo declara Master Plan). |
| `tests/` | 24 archivos `test_*.py`, con fixtures sintéticos/fakes y pruebas unitarias/de integración por dominio. Conteo estático: 183 funciones `test_*` (el total de ejecuciones parametrizadas puede ser mayor). | Pytest configura `testpaths=["tests"]`, `pythonpath=["."]`, `addopts=["-ra"]`; CI `.github/workflows/tests.yml` instala `.[dev]` y corre `python -m pytest` en Python 3.12. | Todos los archivos listados en la sección 7. | Cobertura prevista amplia; resultado de ejecución pendiente/bloqueado en esta máquina, no se puede certificar cobertura ni passing. |
| `docs/` / raíz | `README.md`, `docs/architecture.md`, `docs/MASTER_PLAN.md`, `docs/application_tools.md`, `docs/performance_metrics.md`, `docs/FINAL_ARCHITECTURE_REVIEW.md`; manifest `pyproject.toml`; `.gitignore`. | README/Architecture/Master Plan describen el sistema; workflow GitHub Actions corre suite. | Sin tests de documentación detectados. | Documentación amplia, con inconsistencias concretas descritas en §5. |

## 4. Dependencias y llamadas entre módulos

### 4.1 Dependencias de runtime declaradas

En `pyproject.toml`, Python `>=3.11`; dependencias runtime:

- `yfinance>=0.2.54`: provider Yahoo en `data/providers/yahoo_finance.py`.
- `scipy>=1.11`: solver SLSQP en `portfolio/optimizer.py`.
- `hmmlearn>=0.3.2`: `GaussianHMM` en `regime/hmm.py`.
- `vaderSentiment>=3.3.2`: inicialización del scorer VADER en
  `sentiment/vader.py`.
- `xgboost>=2.1`: clasificador en `models/xgboost_model.py`.
- Dev: `pytest>=8.0`.

No se declara LangGraph, SDK de LLM, framework web, broker o fuente de noticias.
GitHub Actions usa Python 3.12, instala el paquete en editable con `.[dev]` y
ejecuta pytest.

### 4.2 Grafo de dependencias observado

- `data.engine` → `data.market_data`, `data.storage` → `MarketDataProvider`
  inyectado → Yahoo provider opcional de producción.
- `features.engine` → `data.market_data`.
- `factors.momentum` → `features.engine`, `config.momentum`.
- `regime.engine` → `features.engine`, `config.regime`; `regime.hmm` →
  `data.market_data`, `hmmlearn`; `regime.comparison` combina resultados.
- `signals.trend` → `features.engine`; `strategies` → signal/factor/regime
  contract; `backtest.engine` → data y `TargetPosition`.
- `risk` recibe escalares/limits/series y es invocado por la estrategia de
  aplicación; no depende del backtest para emitir decisiones.
- `portfolio` usa retornos del caller; solo optimizer depende de SciPy.
- `evaluation.metrics` → backtest types; benchmark → backtest; walk-forward →
  splits + backtest/evaluation.
- `sentiment` usa news items y FeatureSeries; `models` usa MarketData,
  FeatureSeries y targets.
- `application.services.research` compone data → features → momentum →
  determinista regime; `strategy_research` compone data, universe, features,
  momentum, regime, signals/strategies, risk, equal weight, backtest,
  evaluation, reporting y experiments.
- `agents.research` → service multi-asset + adapters de comparison/reporting;
  no llama a las herramientas `backtest`, `risk` o `portfolio` del paquete
  Application Tools, ni a execution.

Los imports vistos apuntan de servicios hacia dominio y no se identificó un
ciclo intencional de dependencias. Esta observación estática no sustituye un
import test ejecutado.

## 5. Gaps, duplicidades, riesgos técnicos y deuda

### 5.1 Gaps funcionales

1. **Portfolio multi-asset:** el servicio usa Equal Weight y combina backtests
   de sleeves; no es una simulación de cartera consolidada con rebalanceo,
   costos/efectivo común y riesgo de portfolio.
2. **Walk-forward:** existe `run_walk_forward`, pero el CLI, service y agente
   no lo exponen como flujo de validación.
3. **ML y sentiment:** APIs standalone; no hay integración a señales,
   estrategias, research CLI o backtest.
4. **HMM:** análisis y comparación standalone; las decisiones estratégicas
   consumen solo el regime determinista.
5. **Fundamentals:** contratos/métricas/ranking existen; no hay provider real
   de datos fundamentales.
6. **Universe:** no hay fuente externa de universo; el pipeline crea universo
   de los símbolos ingresados y, para su adapter interno, configura
   `minimum_history=1`.
7. **Paper execution:** funciona de forma independiente; ninguna herramienta o
   agente lo orquesta. No hay broker real, intencionalmente.
8. **Application UI/API:** `app/` solo contiene el marcador de paquete; no hay
   frontend ni API de servicio.
9. **Test suite:** 24 módulos de prueba están presentes, pero hasta ejecutar
   pytest no hay evidencia runtime de aceptación.

### 5.2 Inconsistencias de documentación

- `README.md` primero dice que “no se implementan agentes” y después describe
  `agents.research` como agente implementado. La lectura consistente es que sí
  existe un orquestador determinista, sin LLM.
- `docs/MASTER_PLAN.md` afirma que el Market Data Engine “ordena las barras
  cronológicamente”; `data.market_data.normalize_market_data` conserva el
  orden de entrada y rechaza timestamps fuera de orden. La documentación debe
  describir validación, no ordenar, salvo que el comportamiento cambie
  explícitamente.
- El nombre “ResearchReport” se usa para dos contratos distintos:
  `application.services.research.ResearchReport` y
  `reporting.research_report.ResearchReport`. Sus responsabilidades son
  diferentes (vista single-asset legada frente a reporte serializable general),
  pero el nombre compartido puede confundir imports y evoluciones.
- El MASTER_PLAN llama al application layer y pipeline `PARTIAL`; eso refleja
  adecuadamente la falta de cartera consolidada y la suite pendiente. No
  declarar fases `COMPLETE` solo por existir módulos.

### 5.3 Duplicidades

- Dos servicios y dos modelos `ResearchReport` se ocupan de proyecciones de
  research diferentes. No se demuestra duplicación de los cálculos base:
  ambos reutilizan `calculate_features`, `rank_momentum` y `detect_regime`.
  Conviene decidir si el informe legacy debe adaptarse al modelo de
  `reporting/`, pero no hacerlo sin requerimiento de compatibilidad.
- Hay dos entry points de research (`research_asset.py` single-asset y
  `run_strategy_research.py` multi-asset), con finalidad diferenciada y tests
  propios; no son duplicados exactos.
- No se identificó por esta revisión evidencia suficiente para declarar otros
  motores cuantitativos duplicados. Helpers de validación por dominio no se
  consideran duplicidad funcional demostrada.

### 5.4 Riesgos técnicos / deuda

- `application.services.strategy_research.run_strategy_research` captura
  `Exception` en torno a `run_market_data_engine` y lo envuelve como
  `MarketDataDownloadError`; puede ocultar la categoría de un error interno
  bajo un mensaje de fallo de descarga. El error original queda como causa.
- `run_strategy_research` escribe los tres formatos de reporte antes de
  registrar el experimento. Un fallo en el registro puede dejar reportes sin
  metadata asociada; los tres archivos tampoco se publican como una transacción
  conjunta.
- `evaluation.run_walk_forward` acepta un evaluator callback. La separación
  temporal de los argumentos es explícita, pero no puede asegurar que el
  callback calcule indicadores/posiciones causalmente dentro de cada ventana.
- Las series y thresholds se leen de archivos/env y varias salidas se escriben
  en disco; el alcance de directorios y tratamiento de errores debe seguir
  validándose en las fronteras de aplicación. El agente restringe paths
  relativos/traversal/symlinks, pero no los fija a un directorio raíz de
  configuración.
- Un archivo versionado `Usuarios.lnk` en la raíz parece ajeno al código y su
  propósito no está explicado. No se inspecciona el destino ni se elimina.
- El agente “agentic” es en realidad un orquestador determinista sin LLM, por
  diseño. Mantener esta distinción clara en README evita expectativas
  equivocadas.

## 6. Archivos que realmente se propondría modificar

No se propone ningún cambio productivo en esta auditoría. Los siguientes son
los puntos de edición mínimos **solo si se aprueba después una tarea concreta**:

| Prioridad / objetivo futuro | Archivos candidatos | Justificación y límites |
|---|---|---|
| Corregir descripciones factuales | `README.md`, `docs/MASTER_PLAN.md` | Resolver la contradicción “no agentes” vs agente determinista y cambiar la afirmación de ordenamiento del Market Data Engine. Solo documentación. |
| Validación OOS integrada | `application/services/strategy_research.py`, `scripts/run_strategy_research.py`, `tests/test_strategy_research.py` | Añadir una opción explícita para ejecutar walk-forward y reportar OOS; conservar `evaluation/` actual y mantener modo histórico actual. Requiere definición de ventanas/metricas por el usuario. |
| Riesgo/contabilidad de cartera consolidada | `application/services/strategy_research.py`, `tests/test_strategy_research.py` y, si el contrato cambia, `backtest/` | Reemplazar la agregación de sleeves por contabilidad de portfolio solo tras fijar cash común, rebalances y política de costos. No es un cambio quirúrgico sin requisitos adicionales. |
| Errores en la frontera de datos | `application/services/strategy_research.py`, `tests/test_strategy_research.py` | Limitar el catch amplio a excepciones esperadas del provider/IO y preservar otros errores, con tests que aseguren mensajes y causas. |
| Unificar modelos de reporte | `application/services/research.py`, `reporting/research_report.py`, `scripts/research_asset.py`, tests de research/reporting | Solo si se decide retirar/adaptar el contrato single-asset legacy; implica compatibilidad de CLI y no es necesario para la auditoría. |
| Aplicación HTTP/UI | `app/` y tests nuevos | No existe todavía. Solo crear si se define producto/contrato; no duplicar `application/tools`. |

No se propone cambiar `features/`, `factors/`, señales o motores existentes ni
crear carpetas alternativas. El alcance pedido se limita a este mapa AS-IS.

## 7. Pruebas existentes y estado de ejecución

Inventario estático: 24 módulos, 183 definiciones `test_*` contadas en el
árbol. Los archivos cubren:

| Tests | Cobertura identificable |
|---|---|
| `tests/test_market_data.py` | Normalización, timestamps, validación, persistencia, engine, CLI y provider falso. |
| `tests/test_features.py` | Features, warm-up/NaNs, valores planos/volumen cero e CLI local. |
| `tests/test_momentum.py` | Horizontes, pesos, empates, validación, entorno y CLI. |
| `tests/test_regime.py`, `tests/test_regime_hmm.py` | Clasificación determinista y contrato HMM/reproducibilidad/comparación. |
| `tests/test_fundamental.py`, `tests/test_universe.py` | Métricas/ranking fundamental y selección/filtros/proveedores falsos. |
| `tests/test_sentiment.py`, `tests/test_models.py` | Sentimiento point-in-time; targets, splits, scaler, baseline, XGBoost y métricas. |
| `tests/test_signals.py`, `tests/test_strategies.py` | Señales, estrategias, límites, registro y determinismo. |
| `tests/test_risk.py`, `tests/test_portfolio.py` | Decisiones de riesgo y allocation/constraints/covariance/optimizer. |
| `tests/test_backtest.py`, `tests/test_walk_forward.py` | Ejecución next-bar, costes, métricas/benchmark y folds temporales/OOS. |
| `tests/test_execution.py` | Paper buy/sell, balances, costes, validación y determinismo. |
| `tests/test_reporting.py`, `tests/test_experiments.py` | Serialización/formato/escaping y fingerprint, persistencia/no overwrite. |
| `tests/test_application_tools.py`, `tests/test_strategy_research.py` | Adapters y pipeline integrado con fake providers, fechas, errores, reports/experiments. |
| `tests/test_research_asset.py`, `tests/test_research_agent.py` | Compatibilidad del CLI single-asset, agente determinista, dry-run, allowlist y evidencia. |
| `tests/test_import_characterization.py`, `tests/test_smoke.py` | Efectos laterales al importar y defaults de Settings. |

### Resultado de ejecución (rellenado con la ejecución real)

| Comando | Tests passed | Tests failed | Warnings | Error / estado |
|---|---:|---:|---:|---|
| `python -m pytest` | No ejecutado | No ejecutado | No reportados | **BLOCKED** antes de iniciar pytest: Windows Application Control bloqueó `python.exe` (`NativeCommandFailed`). |
| `py -3.12 -m pytest` | No ejecutado | No ejecutado | No reportados | **BLOCKED** antes de iniciar pytest: Windows Application Control bloqueó `d:\users\jvicenth\AppData\Local\Programs\Python\Python312\python.exe` (launcher exit code 101). |

La suite queda **BLOCKED / no ejecutada**; no hubo resultados de tests,
warnings de pytest o fallos de tests que puedan reportarse. No interpretar esto
como `0 passed` de una ejecución completada ni inferir failures de tests.
