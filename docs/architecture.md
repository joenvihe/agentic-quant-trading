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
- `features/`: futuras transformaciones de datos y variables derivadas.
- `factors/`: futuros factores cuantitativos.
- `regime/`: futuros análisis de regímenes de mercado.
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

Este milestone no calcula indicadores o momentum, no identifica regímenes, no
predice precios, conecta brokers, envía órdenes, gestiona dinero real ni incluye
LLMs, LangGraph o agentes autónomos.
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

- `data/`: futura carga, validación y almacenamiento de datos de mercado.
- `features/`: futuras transformaciones de datos y variables derivadas.
- `factors/`: futuros factores cuantitativos.
- `regime/`: futuros análisis de regímenes de mercado.
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

## Límites de la primera fase

Este repositorio solo establece el esqueleto del núcleo cuantitativo. No
conecta brokers, envía órdenes, gestiona dinero real ni incluye ejecución
automática. Tampoco incorpora todavía LLMs, LangGraph o agentes autónomos.
