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
  TICKER` orquesta el proveedor, la validación y la persistencia.
- `features/`: Quant Feature Engine calcula indicadores exclusivamente sobre
  el contrato OHLCV normalizado de `data/`.
- `factors/`: Momentum Engine rankea activos usando retornos y percentiles;
  no produce señales ni operaciones.
- `regime/`: Market Regime Engine clasifica dirección, fuerza, volatilidad y
  confirmación con reglas deterministas y thresholds configurables.
- `strategies/`: futuras hipótesis y señales de investigación; no contiene
  estrategias todavía.
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

Los paquetes no dependen entre sí en esta fase. A medida que se añada
funcionalidad, las dependencias deben fluir desde las capas de aplicación hacia
componentes de dominio más pequeños, evitando ciclos.

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
envían órdenes, gestionan dinero real ni incluyen LLMs, LangGraph o agentes
autónomos.

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
