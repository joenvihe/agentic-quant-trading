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
  confirmación con reglas deterministas y thresholds configurables.
- `signals/`: contratos de señales y generadores que consumen resultados de
  features existentes. `MovingAverageCrossSignal` lee SMA disponibles, opera
  en modo long-only y no descarga datos.
- `strategies/`: contratos y estrategias deterministas que transforman
  señales/factores y régimen en `TargetPosition`. Incluye el mapeo
  `MovingAverageStrategy`, la estrategia long-only `MomentumRegimeStrategy` y
  un `StrategyRegistry` de registro explícito.
- `risk/`: futuras métricas y reglas de análisis del riesgo.
- `backtest/`: futura simulación histórica determinista.
- `portfolio/`: futura agregación y análisis de carteras.
- `evaluation/`: futuras métricas y herramientas de evaluación.
- `agents/`: reservado para una fase posterior; no contiene agentes ni lógica
  de LLM.
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

Estos motores no identifican regímenes, predicen precios, conectan brokers,
envían órdenes ni gestionan dinero real. Tampoco incluyen LLMs, LangGraph o
agentes autónomos.

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

No hay señales SHORT generadas por esta primera regla, backtesting, PnL,
órdenes, brokers ni agentes.

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
