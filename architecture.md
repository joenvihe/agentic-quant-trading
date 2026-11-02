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
