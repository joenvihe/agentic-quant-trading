# Master Plan

## Current repository assessment

Status labels describe implemented behavior, not directory names:

- **[EXISTS] Market Data Engine:** `data/market_data.py`, `data/engine.py`, `data/storage.py`, and `data/providers/yahoo_finance.py` define normalized OHLCV records, provider and data contracts, validation, CSV persistence, and the Yahoo Finance adapter. The provider is an external runtime dependency; quantitative modules consume the normalized model rather than fetching data.
- **[EXISTS] Data validation:** validation is part of `normalize_market_data` and the Market Data Engine; there is no separate validation package. It checks ticker and row shape, timestamps/order/duplicates, finite and positive prices, OHLC consistency, and volume.
- **[EXISTS] Quant Feature Engine:** `features/engine.py` calculates trend, momentum, volatility, volume, and market-structure features from normalized market data. Insufficient lookback windows produce missing values rather than fabricated values.
- **[EXISTS] Momentum factor:** `factors/momentum.py` computes horizon returns, absolute momentum, cross-sectional relative ranks, and configurable composite scores. A single-asset research report cannot compute cross-sectional scores and reports them as unavailable.
- **[EXISTS] Deterministic Market Regime baseline:** `regime/engine.py` classifies regimes using explicit configurable thresholds, metrics, evidence, and reason codes. This is a baseline, not an HMM or a trading recommendation.
- **[EXISTS] Configuration primitives:** `config/settings.py`, `config/momentum.py`, and `config/regime.py` provide application settings and environment-configurable factor/regime parameters.
- **[PARTIAL] Logging:** `config/logging_config.py` provides explicit logging configuration; logging policy and consistent use across all application boundaries remain to be established.
- **[PARTIAL] Application and reporting:** `application/services/research.py` orchestrates the current single-asset research flow and `scripts/research_asset.py` renders a console report. It does not implement signals, strategies, backtests, portfolio construction, or a full reporting/experiment system.
- **[PARTIAL] Signals + strategies:** `signals/` provides validated signal values and a long-only moving-average signal using existing SMA features. `strategies/` maps signals and existing momentum/regime outputs into target positions and has an explicit registry. Phase 1 acceptance awaits a successful full-suite run.
- **[PARTIAL] Backtest + evaluation:** a deterministic daily, single-asset, long-only engine with next-bar execution and transaction costs is implemented, along with performance metrics and a causal Buy and Hold benchmark. Phase 2 acceptance awaits a successful full-suite run.
- **[PARTIAL] Walk-forward validation:** `evaluation/` provides expanding/rolling temporal splits, train-only parameter selection, test-only evaluation, and OOS robustness summaries. Full-suite validation remains pending.
- **[PARTIAL] Risk Engine:** `risk/` provides explicit exposure limits, optional volatility targeting, and drawdown circuit-breaker decisions without executing trades or selecting strategies. Full-suite validation remains pending.
- **[PARTIAL] Portfolio:** `portfolio/` implements equal-weight allocation, sample covariance from aligned return series, and long-only maximum-Sharpe optimization with explicit bounds. Full-suite validation remains pending.
- **[TODO] Agent and application tools:** `agents/` and `app/` contain package markers only; there is no agent runtime or application-tool layer.
- **[TODO] HMM regime, fundamental analysis, universe selection, sentiment, supervised ML, experiment tracking, and paper trading:** no implementations are present.
- **[BLOCKED] Real broker execution:** explicitly outside the current scope. Do not add it without a separate, explicit authorization and safety review; no credentials or real trading operations belong in this repository.

### Existing contracts and conventions

- The core data contract is `MarketBar`, `MarketData`, and `MarketDataProvider` in `data/market_data.py`. The engine normalizes tickers, orders bars chronologically, validates the normalized data, persists it, and reloads it.
- Data exceptions are `MarketDataError`, `MarketDataDownloadError`, and `MarketDataValidationError`. Quantitative modules expose their own domain errors, including feature, momentum, and regime errors; application services translate expected failures for their CLI boundary.
- The flow currently implemented is: ticker → Market Data Engine → normalized `MarketData` → Feature Engine → Momentum factor and Regime Engine → research service → console report.
- Python 3.11 or newer is required. Runtime dependencies: `yfinance` and SciPy (for portfolio optimization); development dependency: `pytest`. Packaging uses setuptools and the CI workflow runs pytest.
- Code uses type hints, dataclasses (including immutable result/configuration objects), explicit domain errors, snake_case names, and pytest. Existing tests use synthetic rows and fake providers; preserve their offline behavior.
- Relevant tests include `tests/test_market_data.py`, `tests/test_features.py`, `tests/test_momentum.py`, `tests/test_regime.py`, `tests/test_research_asset.py`, `tests/test_signals.py`, `tests/test_strategies.py`, `tests/test_backtest.py`, `tests/test_walk_forward.py`, `tests/test_risk.py`, and `tests/test_smoke.py`.
- The package markers in `agents/` and `app/` do not indicate implemented capabilities.

### Current regression coverage

The existing offline pytest suite characterizes Market Data normalization and
validation (including duplicate/out-of-order timestamps and invalid OHLC),
feature windows and insufficient history, momentum rankings and configurable
weights, regime thresholds and the allowed regime states, and research CLI
success/failure behavior. Research CLI provider failures are asserted not to
show tracebacks.

Additional characterization coverage confirms chronological normalized
timestamps, the momentum result contract contains ranking/factor fields rather
than order fields, repeated reports from identical synthetic history are
byte-for-byte stable, and importing the current modules neither configures
logging nor attempts provider/network access. These tests use synthetic data,
fake providers, or a guarded subprocess; they do not depend on live market data.
Phase 1 adds offline tests for signal states/validation, insufficient SMA
history, strategy position mapping, allowed-regime gating, explicit registry
behavior, and deterministic strategy outputs.
Phase 2 adds synthetic tests for flat and buy/hold curves, delayed execution,
entry/exit accounting, transaction costs, input validation, defined metric
values, benchmark comparison, and deterministic results.
Phase 3 adds synthetic temporal split and callback-isolation tests, insufficient
history checks, risk limit/volatility/drawdown/configuration tests, and
determinism checks.

## Target architecture

Keep responsibilities separated and data flow explicit:

Data
→ Features
→ Factors
→ Signals
→ Strategies
→ Risk
→ Portfolio
→ Backtest
→ Evaluation
→ Reporting
→ Execution

Agents orchestrate these capabilities; they do not replace quantitative logic. Implement roadmap phases incrementally, preserve the current working path, avoid look-ahead/data leakage, and keep tests deterministic and offline.

## Roadmap

### Phase 1 — Signals + Strategies [PARTIAL]

- **Objective:** Define explicit signal contracts and implement initial strategies that consume existing factors/features without conflating factors, signals, target positions, and orders.
- **Modules affected:** `signals/`, `strategies/`, `pyproject.toml` package discovery, documentation, and tests. Existing feature/factor/regime engines remain unchanged.
- **Dependencies:** Existing `FeatureSeries`, `MomentumRank`, and `RegimeAssessment` contracts. The moving-average signal supports only SMA periods already emitted by Feature Engine; the momentum/regime strategy uses positive 12M absolute momentum and defaults to `BULL_STRONG` and `BULL_VOLATILE`, with a configurable allowlist.
- **Tests required:** `tests/test_signals.py` and `tests/test_strategies.py` cover LONG/FLAT, insufficient history, invalid windows, strength boundaries, position mapping, registry and duplicate names, regime gating, input validation, and determinism. The complete pytest suite must pass.
- **Acceptance:** Implemented contracts and strategies return typed, timezone-aware signals/target positions; no broker calls, orders, PnL, backtesting, or quantitative duplication in CLI code. Mark **COMPLETE only after the full test suite passes**. Current status remains **PARTIAL** while execution is blocked by the local Windows application-control policy.

### Phase 2 — Backtest + Performance Metrics [PARTIAL]

- **Objective:** Evaluate strategy behavior with a reproducible historical simulation and clearly defined performance metrics.
- **Modules affected:** `backtest/`, `evaluation/`, docs, and tests. Phase 1 strategy contract is consumed without modification.
- **Dependencies:** Existing `MarketData` and `TargetPosition` contracts. Daily bars, one asset, long-only target weights [0, 1], no margin or short sales.
- **Tests required:** `tests/test_backtest.py` uses synthetic fixtures for flat and buy/hold results, delayed next-bar execution, entry/exit, costs, invalid prices/capital/positions, flat/known drawdown metrics, undefined no-trade metrics, benchmark and determinism. The complete pytest suite must pass.
- **Acceptance:** Closing-bar decisions execute no earlier than the next bar's open; purchases cannot create margin; costs and metric conventions are documented; identical inputs produce identical results. Current status remains **PARTIAL** while full-suite execution is blocked by the local Windows application-control policy. Mark **COMPLETE only after the full suite passes**.

### Phase 3 — Walk-Forward Validation + Risk [PARTIAL]

- **Objective:** Add out-of-sample, time-ordered validation and explicit risk constraints.
- **Modules affected:** `evaluation/splits.py`, `evaluation/walk_forward.py`, `evaluation/robustness.py`, `risk/`, documentation, and tests. No portfolio modules or backtest behavior modified.
- **Dependencies:** Existing `MarketData`, `BacktestResult`, and `PerformanceMetrics` contracts. The evaluator callback receives one chronological partition at a time; parameter candidates are explicit and selected by optimizing a configured train metric (maximize by default, optionally minimize). Risk receives requested weight, current exposure, optional annualized realized volatility, and optional positive-fraction drawdown.
- **Tests required:** `tests/test_walk_forward.py` covers expanding/rolling boundaries, insufficient history, train/test callback isolation, selection and OOS evaluation. `tests/test_risk.py` covers strategy approval, per-asset and aggregate exposure limits, volatility targeting, drawdown blocking, invalid configuration/inputs, and determinism. The complete pytest suite must pass.
- **Acceptance:** Splits are ordered and disjoint (`train_end < test_start`), candidates are selected only on train, and only the selected candidate is evaluated on test. Risk returns explicit approved/reduced/rejected weights and reasons, without strategy selection or execution. Current status remains **PARTIAL** while full-suite execution is blocked by the local Windows application-control policy. Mark **COMPLETE only after the full suite passes**.

### Phase 4 — Portfolio Optimization [PARTIAL]

- **Objective:** Allocate portfolio weights deterministically and optimize long-only maximum Sharpe subject to explicit constraints.
- **Modules affected:** `portfolio/`, documentation, dependency manifest, and tests. The implementation is standalone and does not alter Risk, Backtest, or Evaluation behavior.
- **Dependencies:** Caller-provided, aligned normalized return series; SciPy `>=1.11` is required for its constrained nonlinear SLSQP solver. SciPy was not present in the declared dependencies or inspected Python environment; it is added because the maximum-Sharpe objective is fractional and nonlinear under box and full-investment constraints. Equal-weight and covariance calculations use only the standard library.
- **Tests required:** `tests/test_portfolio.py` covers equal weights and sums, bounds/long-only behavior, dominant asset, singular covariance, insufficient and invalid return history, duplicate symbols, explicit optimizer failure, and determinism. The complete pytest suite must pass.
- **Acceptance:** Successful weights satisfy all configured bounds and sum to one; infeasible inputs or solver failures return explicit failure without silently falling back to equal-weight. Return/covariance assumptions and solver choice are documented. Current status remains **PARTIAL** until the full suite passes.

### Phase 5 — HMM Regime + Fundamental + Universe Selection [TODO]

- **Objective:** Add separately validated regime modeling, point-in-time fundamental data, and a reproducible asset-universe selection process.
- **Modules affected:** `regime/`, new fundamental/universe modules, `data/` provider contracts if needed, configuration, and tests.
- **Dependencies:** Existing normalized data/features; point-in-time data availability and licensing/provenance requirements; model and universe-selection specifications.
- **Tests required:** Synthetic regime sequences and state mapping tests; provider fakes; stale/missing fundamental data tests; survivorship/look-ahead checks; deterministic behavior for fixed model configuration.
- **Acceptance:** The current deterministic baseline remains available; new model/fundamental/universe outputs are explicitly versioned, interpretable where possible, and cannot silently replace existing behavior.

### Phase 6 — Reporting + Experiment Tracking [TODO]

- **Objective:** Produce reusable structured research outputs and record the inputs/configuration/code version needed to reproduce an experiment.
- **Modules affected:** `application/`, reporting modules, `evaluation/`, configuration, and tests.
- **Dependencies:** Stable outputs from the implemented quantitative phases.
- **Tests required:** Schema/serialization tests, unavailable-value handling, reproducibility metadata checks, and offline storage tests.
- **Acceptance:** A report links results to their data range, configuration, and code identity; serialization is stable and does not invent missing values.

### Phase 7 — Sentiment + Supervised ML [TODO]

- **Objective:** Add optional sentiment and supervised models only after defining point-in-time inputs, labels, and evaluation methodology.
- **Modules affected:** New sentiment/model modules, `data/` provider contracts as necessary, `features/` or `factors/` only for well-defined outputs, and `evaluation/`.
- **Dependencies:** Phases 2, 3, and 6; approved data provenance, label construction, leakage controls, and dependency review.
- **Tests required:** Offline provider fakes; label alignment and leakage tests; deterministic preprocessing/model tests where supported; baseline comparison and unavailable-data tests.
- **Acceptance:** Model outputs are clearly distinguished from factors and signals; evaluation is out of sample and reproducible; optional dependencies and data assumptions are documented.

### Phase 8 — Paper Trading [TODO]

- **Objective:** Validate strategy-to-order lifecycle in a paper/sandbox environment without real trading.
- **Modules affected:** New paper execution adapter, `application/`, `risk/`, configuration, and integration tests.
- **Dependencies:** Phases 1–3, explicit order/risk contracts, and a sandbox-only provider with a clear operational safety boundary.
- **Tests required:** Fake broker/sandbox tests, order-state transition tests, idempotency and failure/retry cases, risk-limit enforcement, and proof that test runs cannot reach a live endpoint.
- **Acceptance:** Only sandbox/paper operations are possible by default; order lifecycle and failures are observable; no real credentials or live trading path are added.

### Phase 9 — Application Tools [TODO]

- **Objective:** Provide stable user-facing tools for invoking and inspecting research workflows without moving business logic into the interface.
- **Modules affected:** `app/`, `application/`, `scripts/`, configuration, and documentation.
- **Dependencies:** Stable service contracts and report formats from prior phases.
- **Tests required:** CLI/API contract tests with injected services; input/error handling tests; offline integration tests; import-side-effect tests.
- **Acceptance:** Tools delegate to application services, provide clear errors and structured output, and perform no downloads or external actions merely by being imported.

### Phase 10 — Research Agent [TODO]

- **Objective:** Add an agent that plans and orchestrates approved research capabilities while leaving quantitative calculations to deterministic modules.
- **Modules affected:** `agents/`, `application/`, approved tools, configuration, and tests.
- **Dependencies:** Stable service/tool contracts, reporting and experiment metadata, and explicit permissions/safety boundaries.
- **Tests required:** Tool-contract and orchestration tests with fakes; permission-boundary tests; deterministic workflow tests where applicable; tests proving the agent cannot bypass risk controls or invoke real trading.
- **Acceptance:** The agent only composes authorized capabilities, records its inputs/actions, surfaces uncertainty and errors, and cannot replace quantitative logic or execute real trades.
