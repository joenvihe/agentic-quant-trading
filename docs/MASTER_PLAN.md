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
- **[PARTIAL] Application and reporting:** `application/services/research.py` and `scripts/research_asset.py` preserve the single-asset research flow. `application/services/strategy_research.py` and `scripts/run_strategy_research.py` compose the existing multi-asset modules through evaluation, reports, and experiment tracking using injected providers. The backtest aggregates equal-capital single-asset sleeves on common timestamps; portfolio-level drawdown/risk accounting remains limited.
- **[PARTIAL] Signals + strategies:** `signals/` provides validated signal values and a long-only moving-average signal using existing SMA features. `strategies/` maps signals and existing momentum/regime outputs into target positions and has an explicit registry. Phase 1 acceptance awaits a successful full-suite run.
- **[PARTIAL] Backtest + evaluation:** a deterministic daily, single-asset, long-only engine with next-bar execution and transaction costs is implemented, along with performance metrics and a causal Buy and Hold benchmark. Phase 2 acceptance awaits a successful full-suite run.
- **[PARTIAL] Walk-forward validation:** `evaluation/` provides expanding/rolling temporal splits, train-only parameter selection, test-only evaluation, and OOS robustness summaries. Full-suite validation remains pending.
- **[PARTIAL] Risk Engine:** `risk/` provides explicit exposure limits, optional volatility targeting, and drawdown circuit-breaker decisions without executing trades or selecting strategies. Full-suite validation remains pending.
- **[PARTIAL] Portfolio:** `portfolio/` implements equal-weight allocation, sample covariance from aligned return series, and long-only maximum-Sharpe optimization with explicit bounds. Full-suite validation remains pending.
- **[PARTIAL] Application tools:** `scripts/run_strategy_research.py` provides an injectable CLI and service for the existing quantitative pipeline without an LLM. General application APIs and `app/` tools remain unimplemented.
- **[PARTIAL] Quant Research Agent:** `agents/research/` provides deterministic structured-request planning, an explicit tool/strategy allowlist, dry-run, traceable calls/evidence, multi-strategy comparison, and evidence-based reporting. It uses no LLM or LangGraph. Full-suite validation remains pending.
- **[PARTIAL] HMM regime:** `regime/hmm.py` adds seeded Gaussian HMM states and statistical labels alongside the deterministic baseline; regime comparison is implemented. Full-suite validation remains pending.
- **[PARTIAL] Fundamental Engine:** provider/snapshot contracts, ROC, Earnings Yield, P/E, and a combined ranking are implemented. No external fundamental provider is included; full-suite validation remains pending.
- **[PARTIAL] Universe Selection:** static symbol provider, normalization/deduplication, injected data provider, and configurable screening filters are implemented. Full-suite validation remains pending.
- **[PARTIAL] Reporting:** `reporting/` builds structured JSON, CSV, and escaped HTML reports from backtest results, existing metrics, and benchmark comparisons. Full-suite validation remains pending.
- **[PARTIAL] Experiment Tracking:** `experiments/` provides canonical data fingerprints and atomic, exclusive JSON metadata storage with best-effort Git version and sensitive-key redaction. Full-suite validation remains pending.
- **[PARTIAL] Sentiment + supervised ML:** `sentiment/` provides fake/injected
  news providers, VADER scores, trailing aggregation and point-in-time
  alignment. `models/` builds forward direction targets from existing
  features, performs purged chronological splits, fits a train-only
  standardizer for its logistic baseline, provides seeded XGBoost, and reports
  classification metrics. Full-suite validation remains pending; no real news
  provider or trading signal/order conversion is included.
- **[PARTIAL] Paper execution:** `execution/` defines order/status contracts, a broker protocol, immutable positions/account snapshots, and an in-memory deterministic `PaperBroker` for market buys/sells using only caller-supplied prices. No broker integration, network, credentials, signals, or strategy decisions are present. Full-suite validation remains pending.
- **[BLOCKED] Real broker execution:** explicitly outside the current scope. Do not add it without a separate, explicit authorization and safety review; no credentials or real trading operations belong in this repository.

### Existing contracts and conventions

- The core data contract is `MarketBar`, `MarketData`, and `MarketDataProvider` in `data/market_data.py`. The engine normalizes tickers and timestamps, validates that input bars are already in chronological order (rejecting out-of-order bars rather than silently sorting them), persists valid data, and reloads it.
- Data exceptions are `MarketDataError`, `MarketDataDownloadError`, and `MarketDataValidationError`. Quantitative modules expose their own domain errors, including feature, momentum, and regime errors; application services translate expected failures for their CLI boundary.
- `scripts/research_asset.py` remains the single-ticker report path. The multi-asset service adds: explicit universe → Market Data Engine/validation → features → momentum factor/ranking → regime → strategy signal/position → per-asset Risk Engine → `EqualWeightAllocator` → single-asset backtests in equal-capital sleeves aggregated on common timestamps → performance and benchmark comparison → JSON/CSV/HTML report → experiment registry. This is not yet a consolidated portfolio with shared cash, rebalancing, and global drawdown. Existing modules perform calculations; this flow has no LLM, paper broker, or real order execution.
- The two public `ResearchReport` types are intentionally distinct: `application.services.research.ResearchReport` is the single-asset research summary, while `reporting.research_report.ResearchReport` is the structured report model for backtest/benchmark results and generated artifacts. Both names remain unchanged for compatibility.
- Python 3.11 or newer is required. Runtime dependencies: `yfinance`, SciPy
  (portfolio optimization), `hmmlearn` (HMM regime analysis), VADER and
  XGBoost (Phase 7); development dependency: `pytest`. Packaging uses
  setuptools and CI runs pytest.
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

Additional characterization coverage confirms normalized timestamps, rejects
out-of-order input bars, the momentum result contract contains ranking/factor
fields rather than order fields, repeated reports from identical synthetic
history are byte-for-byte stable, and importing the current modules neither
configures logging nor attempts provider/network access. These tests use
synthetic data, fake providers, or a guarded subprocess; they do not depend on
live market data.
Phase 1 adds offline tests for signal states/validation, insufficient SMA
history, strategy position mapping, allowed-regime gating, explicit registry
behavior, and deterministic strategy outputs.
Phase 2 adds synthetic tests for flat and buy/hold curves, delayed execution,
entry/exit accounting, transaction costs, input validation, defined metric
values, benchmark comparison, and deterministic results.
Phase 3 adds synthetic temporal split and callback-isolation tests, insufficient
history checks, risk limit/volatility/drawdown/configuration tests, and
determinism checks.
Phase 4 adds synthetic allocation, covariance, constraints, optimizer failure,
and determinism tests.
Phase 5 adds synthetic seeded-HMM, regime-comparison, fundamental metrics and
ranking, point-in-time provider, and universe-filter tests.
Phase 6 adds offline tests for reports with/without trades, JSON/CSV/HTML,
escaping, benchmark comparisons, stable data fingerprints, atomic writes,
loading, redaction, and overwrite prevention.
Phase 7 adds fake-news and causal sentiment alignment tests, forward-target
and timestamp checks, purged chronological dataset splits, train-only scaling,
baseline/XGBoost reproducibility, and classification metric coverage.
Phase 8 adds offline paper-broker tests for buys/sells, insufficient funds,
overselling, commission/slippage, account marking, invalid prices, duplicate
order IDs and deterministic results.
Phase 9 adds offline multi-asset pipeline integration tests with an injected
market-data provider, including report and experiment outputs, date filtering
with prior-history feature warm-up, strategy parameter reporting, cost
configuration, hidden tracebacks, and CLI exit codes.
Application-tool tests cover fake-provider research, causal backtests,
timestamp-aligned strategy comparison, risk decisions, explicit optimizer
failures, serializable responses, trace ID validation, and report path safety.
Phase 10 adds fake-provider agent workflow tests for deterministic tool
selection, multi-strategy comparison, missing-evidence warnings, dry-run,
traceability, serialization, and blocking unapproved tools/strategies.

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

### Phase 5 — HMM Regime + Fundamental + Universe Selection [PARTIAL]

- **Objective:** Add seeded statistical regime analysis, point-in-time fundamental metrics/ranking, and reproducible universe screening without replacing the deterministic baseline or creating orders.
- **Modules affected:** `regime/hmm.py`, `regime/comparison.py`, `fundamental/`, `universe/`, `pyproject.toml`, documentation, import characterization, and tests.
- **Dependencies:** Normalized `MarketData`; caller/provider-supplied fundamentals ranked against an explicit `as_of` cutoff; injected universe metadata also fetched at an explicit cutoff. `hmmlearn>=0.3.2` is added because it provides the requested Gaussian HMM and was absent from the declared dependencies and inspected Python environment. No fundamental or universe data source is added.
- **Tests required:** `tests/test_regime_hmm.py` covers seeded reproducibility, insufficient history, invalid time series, and deterministic/HMM comparison. `tests/test_fundamental.py` covers fake providers, point-in-time cutoff, missing values, ROC/EY/P-E, zero denominators, and combined ranking. `tests/test_universe.py` covers static provider normalization/deduplication, fake market metadata, price/history/missing-data/capitalization filters, and rejection reasons. The complete pytest suite must pass.
- **Acceptance:** The deterministic regime engine remains unchanged and available; HMM labels are based on observed statistics rather than state IDs; fundamental missing values remain unavailable; universe filtering is deterministic and reports reasons. Current status remains **PARTIAL** until the full suite passes.

### Phase 6 — Reporting + Experiment Tracking [PARTIAL]

- **Objective:** Produce reusable JSON/CSV/HTML research reports and record experiment inputs/outputs reproducibly.
- **Modules affected:** `reporting/`, `experiments/`, package discovery, `.gitignore`, documentation, import characterization, and tests.
- **Dependencies:** Existing `BacktestResult`, `PerformanceMetrics`, and `PerformanceComparison` contracts; standard-library serialization/storage only.
- **Tests required:** `tests/test_reporting.py` covers reports without/with trades, format output, escaping, curves, warnings and benchmark comparisons. `tests/test_experiments.py` covers canonical fingerprints, metadata loading, timestamps, redaction, atomic publication failure, path safety, and non-overwrite behavior.
- **Acceptance:** Reports serialize computed results without changing strategy decisions or recomputing metrics; HTML escapes content; writers only run on explicit paths. Experiment metadata is JSON, fingerprints are stable for equivalent inputs, writes publish atomically without overwriting existing IDs, and known secret fields are redacted. Current status remains **PARTIAL** until the full suite passes.

### Phase 7 — Sentiment + Supervised ML [PARTIAL]

- **Objective:** Add point-in-time sentiment features and reproducible binary direction classifiers without converting predictions into orders or interpreting accuracy as returns.
- **Modules affected:** `sentiment/`, `models/`, package discovery, dependencies, import characterization, documentation, and tests. Existing feature/factor/signal/strategy engines remain unchanged.
- **Dependencies:** Normalized `MarketData`, existing causal `FeatureSeries`, temporal validation conventions, and explicit news supplied through an injected provider. VADER and XGBoost were not found in the inspected Python 3.12 site-packages and are added because the requested VADER scorer and XGBoost implementation require them. No live news API or external service is introduced.
- **Tests required:** `tests/test_sentiment.py` covers positive/negative VADER scores, fake provider, absent/future news and timestamp alignment. `tests/test_models.py` covers forward target alignment, missing features, temporal splitting and target-horizon purge, train-only scaling, reproducibility, classifier metrics, and seeded XGBoost. `tests/test_import_characterization.py` checks imports for side effects.
- **Acceptance:** News scores never include items published after feature time; train/test are strictly temporal and training labels are purged at the test boundary; scaler fit uses train only; model results are `MLSignal`, not orders; classification metrics are explicitly not financial performance. Status remains **PARTIAL** until the full suite passes.

### Phase 8 — Paper Trading [PARTIAL]

- **Objective:** Define a safe local paper-execution boundary with explicit orders, account state, deterministic fills, and no real broker activity.
- **Modules affected:** `execution/`, package discovery, documentation, import characterization, and tests. No application-level strategy orchestration or live broker adapter is added.
- **Dependencies:** Explicit caller-created market orders and caller-supplied finite prices; existing backtest cost configuration/calculation is reused for commissions and slippage.
- **Tests required:** `tests/test_execution.py` covers buys/sells, order lifecycle, insufficient funds, overselling, commission/slippage, account equity/mark-to-market, invalid input, duplicate IDs, and determinism. Import characterization ensures no network activity.
- **Acceptance:** Orders are only filled/rejected by an in-memory `PaperBroker`; position exposure is long-only; funds and prices are validated; all price data is explicit and local. No credentials, real broker, network calls, strategy decisions or live operations are included. Status remains **PARTIAL** until the full suite passes.

### Phase 9 — Application Tools [PARTIAL]

- **Objective:** Expose the existing quantitative services through validated, serializable application requests and responses, without duplicating domain logic or allowing tools to invoke arbitrary code.
- **Modules affected:** `application/tools/` (research, backtest, strategy comparison, risk, portfolio optimization, and reporting adapters), `application/services/`, `scripts/run_strategy_research.py`, preserved `scripts/research_asset.py`, documentation, and tests. The broader `app/` interface remains future work.
- **Dependencies:** Existing provider, research service, backtest, evaluation, risk, portfolio, and reporting contracts. No LangGraph, LLM, broker connection, or new dependency is required.
- **Tests required:** `tests/test_application_tools.py` covers each tool, request validation, trace IDs, serializable responses, failures/warnings, safe report paths, and injected fake providers. `tests/test_strategy_research.py` retains multi-asset integration coverage; import characterization checks tools for import-time side effects. Run the full pytest suite.
- **Acceptance:** All tool requests are typed and validated; responses consistently include success, trace ID, serializable data, warnings, and errors; adapters reuse domain services and propagate explicit failures. Reporting is confined to a configured root and blocks traversal/symlink targets. No arbitrary code execution, real trading, LLM, or implicit import-time external effects. Existing multi-asset CLI remains available. Status remains **PARTIAL** until the full suite passes.

### Phase 10 — Research Agent [PARTIAL]

- **Objective:** Orchestrate approved quantitative research capabilities from structured requests while keeping calculations in existing domain services.
- **Modules affected:** `agents/research/` (agent, structured state, static policy, deterministic planner/report renderer), approved `application/tools/` and `application/services/`, import characterization, architecture and user documentation.
- **Dependencies:** Existing multi-asset strategy-research service and typed comparison/reporting tools. `pyproject.toml` already contains all needed runtime dependencies; LangGraph is unnecessary for this fixed, deterministic workflow and no dependency was added.
- **Tests required:** `tests/test_research_agent.py` checks deterministic tool selection, fake-provider execution, multi-strategy comparison, missing metric evidence warnings, policy rejection of unapproved tools/strategies, dry-run side-effect absence, traceability, and serializable outputs. Import characterization includes agent modules. Run the complete pytest suite.
- **Acceptance:** Requests are structured and validated; the fixed allowlist is checked before any side effect; dry-run performs no data access or writes; execution results, comparisons, reports, warnings, and errors are traceable and based on actual domain outputs. No arbitrary code, strategy modification, credentials, LLM, real trading, or claims of future returns. Status remains **PARTIAL** until the full suite passes.
- **Path boundary:** `AQT_RESEARCH_WORKSPACE` configures the workspace root (default `research_workspace`). Request paths are relative to that root; absolute paths, parent traversal, and symlink escapes are rejected.
