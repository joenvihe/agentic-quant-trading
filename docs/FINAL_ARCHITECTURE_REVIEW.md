# Final Architecture Review

## Executive summary

The repository contains a broad, modular quantitative research implementation
covering normalized market data through reporting, experiment tracking,
application adapters, and a deterministic research agent. The main quantitative
boundaries are visible in code: data is normalized before feature calculation,
Momentum is a factor rather than a trade instruction, target positions are
separate from orders, and the backtest executes a close-time decision no sooner
than the next bar.

This is a **static review, not a passing release audit**. Neither the full test
suite, Python compilation, nor the import-characterization test could start:
Windows Application Control blocked both `python.exe` and the Python 3.12
launcher. Consequently, no runtime check is reported as passed, and the
capabilities below remain `PARTIAL` pending execution in an allowed CI/runtime
environment. No product code was changed and no files were deleted.

## Capability status

Status definitions for this review:

- **COMPLETE** — implementation and required verification are both established.
- **PARTIAL** — an implementation is evidenced, but scope or verification is
  incomplete.
- **NOT IMPLEMENTED** — no implementation is present.
- **BLOCKED** — intentionally excluded or prohibited pending separate approval.
- **NOT APPLICABLE** — deliberately not required by the current architecture.

| Capability | Status | Evidence and assessment |
|---|---|---|
| Normalized Market Data and validation | PARTIAL | `MarketBar`, `MarketData`, `MarketDataProvider`, `normalize_market_data`, and `run_market_data_engine` in [data/market_data.py](../data/market_data.py) and [data/engine.py](../data/engine.py). Yahoo is the external provider; the tested contract has offline fake-provider coverage, but it was not executable here. |
| Features, Momentum factor, deterministic regime | PARTIAL | `calculate_features`, `rank_momentum`, and `detect_regime` in [features/engine.py](../features/engine.py), [factors/momentum.py](../factors/momentum.py), and [regime/engine.py](../regime/engine.py). The feature engine does not fetch data; initial history is represented as missing. |
| Signals and Strategies | PARTIAL | `MovingAverageCrossSignal`, `MovingAverageStrategy`, `MomentumRegimeStrategy`, and `StrategyRegistry` in [signals/trend.py](../signals/trend.py), [strategies/moving_average.py](../strategies/moving_average.py), [strategies/momentum_regime.py](../strategies/momentum_regime.py), and [strategies/registry.py](../strategies/registry.py). The boundaries preserve Factor → Signal → Strategy → TargetPosition. |
| Backtest, transaction costs, evaluation, benchmark | PARTIAL | `run_backtest`, `BacktestConfig`, `PerformanceMetrics`, and `buy_and_hold_benchmark` in [backtest/engine.py](../backtest/engine.py), [backtest/types.py](../backtest/types.py), [evaluation/metrics.py](../evaluation/metrics.py), and [evaluation/benchmark.py](../evaluation/benchmark.py). The implemented engine is daily, single-asset, long-only. |
| Temporal splits and walk-forward | PARTIAL | `generate_time_splits`, `slice_market_data`, and `run_walk_forward` in [evaluation/splits.py](../evaluation/splits.py) and [evaluation/walk_forward.py](../evaluation/walk_forward.py). The API separates train selection from test evaluation; caller-supplied callbacks still need to honor the supplied split. |
| Risk Engine | PARTIAL | `evaluate_risk` and `RiskLimits` in [risk/engine.py](../risk/engine.py) and [risk/types.py](../risk/types.py). Risk returns decisions and reasons; it is not an execution system. In multi-asset research, drawdown control is per asset rather than based on one consolidated portfolio curve. |
| Portfolio allocation and optimization | PARTIAL | `EqualWeightAllocator`, `estimate_covariance`, and `MaximumSharpeOptimizer` in [portfolio/allocation.py](../portfolio/allocation.py), [portfolio/covariance.py](../portfolio/covariance.py), and [portfolio/optimizer.py](../portfolio/optimizer.py). The optimizer accepts caller-provided returns and is not the allocation method used in the integrated multi-asset pipeline. |
| HMM regime, fundamentals, universe selection | PARTIAL | `GaussianHMMRegime`, fundamental metric/ranking contracts, and `select_universe` in [regime/hmm.py](../regime/hmm.py), [fundamental/metrics.py](../fundamental/metrics.py), [fundamental/ranking.py](../fundamental/ranking.py), and [universe/service.py](../universe/service.py). No external fundamental provider is included; the universe implementation uses injected providers/static symbols. |
| Reporting and experiment tracking | PARTIAL | JSON/CSV/HTML writers and `ExperimentRegistry` in [reporting/](../reporting/) and [experiments/registry.py](../experiments/registry.py). The roadmap describes escaped HTML, explicit output paths, atomic metadata writes, fingerprints, and sensitive-key redaction; runtime verification remains pending. |
| Sentiment and supervised ML | PARTIAL | `aggregate_sentiment`, `align_sentiment`, `build_ml_dataset`, `temporal_train_test_split`, `BaselineClassifier`, `XGBoostClassifier`, and `evaluate_classifier` in [sentiment/aggregate.py](../sentiment/aggregate.py), [sentiment/alignment.py](../sentiment/alignment.py), [models/datasets.py](../models/datasets.py), [models/baseline.py](../models/baseline.py), and [models/evaluation.py](../models/evaluation.py). No real news provider is included. |
| Paper execution | PARTIAL | `PaperBroker` in [execution/paper.py](../execution/paper.py) uses caller-supplied prices and simulates long-only market orders, fees, and slippage. It is not connected to the research agent or research CLI. |
| Integrated strategy-research pipeline and CLI | PARTIAL | `run_strategy_research` in [application/services/strategy_research.py](../application/services/strategy_research.py), `main` in [scripts/run_strategy_research.py](../scripts/run_strategy_research.py), and the preserved single-asset `main` in [scripts/research_asset.py](../scripts/research_asset.py). The multi-asset path uses equal-capital sleeves and common timestamps, not a fully consolidated portfolio engine. |
| Application tools | PARTIAL | Typed adapters in [application/tools/](../application/tools/); `test_application_tools.py` includes individual adapter and path-safety cases. General UI/API implementation under `app/` is not present beyond its package marker. |
| Quant Research Agent | PARTIAL | `ResearchAgent`, `DeterministicResearchPlanner`, `run_research_agent`, and `authorize_plan` in [agents/research/agent.py](../agents/research/agent.py) and [agents/research/policy.py](../agents/research/policy.py). The allowlist is fixed and excludes execution; the agent uses no LLM. No allowed runtime was available to verify it. |
| Real broker execution | BLOCKED | Explicitly out of scope in [docs/MASTER_PLAN.md](MASTER_PLAN.md); there is no real broker adapter or credential-based execution path. |
| General application UI | NOT IMPLEMENTED | `app/` contains only `__init__.py`; no UI/API capability was found. |
| Deep learning | NOT IMPLEMENTED | No deep-learning framework or model implementation is included. |
| LangGraph | NOT APPLICABLE | The workflow is fixed and deterministic; [pyproject.toml](../pyproject.toml) contains no LangGraph dependency. |

## Review of the requested areas

1. **Architecture and separation of responsibilities:** The modules follow the
   intended distinctions among market data, features, factors, signals,
   strategies, risk, portfolio, backtest, evaluation, reporting, and execution.
   The integrated service composes these modules instead of reimplementing
   feature or factor calculations. `PaperBroker` is not called by either
   research CLI or by `agents.research`.
2. **Dependencies:** `pyproject.toml` requires Python `>=3.11`. The runtime
   dependencies currently are `yfinance>=0.2.54`, `scipy>=1.11`,
   `hmmlearn>=0.3.2`, `vaderSentiment>=3.3.2`, and `xgboost>=2.1`;
   `pytest>=8.0` is a development dependency. Git history for `pyproject.toml`
   shows yfinance introduced with the Market Data Engine, SciPy with portfolio
   optimization, hmmlearn with HMM regime analysis, and VADER/XGBoost with
   sentiment and ML. LangGraph was not added. The manifest's documented reasons
   are portfolio optimization, HMM, sentiment scoring, and boosted trees.
3. **Imports and side effects:** `tests/test_import_characterization.py`
   imports the project modules in a subprocess while trapping logging
   configuration, Yahoo calls, and socket connections. Static searches locate
   market-data requests in explicit provider/engine functions and report/data
   writes in explicit service/writer functions; the characterization test
   could not be run. `config.logging_config.configure_logging` is explicit
   rather than an intended import-time action.
4. **Data leakage and look-ahead:** `build_ml_dataset` aligns each feature row
   with a future target while preserving `feature_timestamp` and
   `target_timestamp`; `temporal_train_test_split` purges training samples
   whose target reaches the test start. `aggregate_sentiment` only includes
   items published within `[as_of - lookback, as_of]`. `run_backtest` applies
   a position generated from close `t` at the next bar; the test
   `test_position_from_close_t_is_executed_at_open_t_plus_one` records this
   invariant. Walk-forward callbacks are temporally separated, but their
   implementations are caller supplied, so causal behavior inside a callback
   cannot be enforced by the split API alone.
5. **Reproducibility:** Randomized model entry points require or accept explicit
   seeds (`GaussianHMMRegime`, `BaselineClassifier`, and `XGBoostClassifier`);
   experiment fingerprints and deterministic research tests exist. Bitwise
   equivalence across platforms/library versions is not established.
6. **Errors and contracts:** Domain exceptions and validation are present, and
   the CLIs return nonzero errors without tracebacks by default. One concern is
   `run_strategy_research` wrapping every `Exception` from
   `run_market_data_engine` as `MarketDataDownloadError`, which can label an
   internal programming/data-validation defect as a download failure. The
   exception is chained, but callers lose the original error category unless
   they inspect it.
7. **Credential and execution safety:** No active credential file or live
   broker integration was found in the reviewed paths. Credential-like keys
   are handled by experiment metadata redaction; `.env` patterns are ignored by
   [.gitignore](../.gitignore). `PaperBroker` needs an explicit price input; the
   agent tool allowlist contains only research, comparison, and reporting.
8. **Public contracts:** The implementation consistently uses dataclasses,
   protocols, validation, and serializable adapter responses. No separate
   API-versioning or compatibility policy was found; external consumers should
   treat these as pre-1.0 contracts.
9. **Documentation and CLI compatibility:** [README.md](../README.md),
   [docs/architecture.md](architecture.md), and [docs/MASTER_PLAN.md](MASTER_PLAN.md)
   document the research boundaries and mark unfinished phases `PARTIAL`.
   `tests/test_research_asset.py` includes
   `test_valid_ticker_runs_pipeline_and_renders_report` and
   `test_report_is_deterministic_for_identical_market_data`; the multi-asset
   CLI has fake-provider integration tests in `tests/test_strategy_research.py`.
   Neither test file was executable in this environment.
10. **Duplication, dead files, and empty folders:** No high-confidence duplicated
    quantitative implementation was established by this static pass; the
    multi-asset service deliberately reuses existing engines. `app/` is a
    package-marker-only placeholder, not a working application surface.
    `Usuarios.lnk` is tracked but its purpose is unexplained and appears
    unrelated to the Python package; it was not removed. No empty top-level
    directories were found.
11. **Overfitting:** Walk-forward and out-of-sample primitives exist, but the
    principal multi-asset CLI and agent do not use them to select or validate
    strategy parameters. The workflow accepts configured parameters and reports
    historical results; it must not be interpreted as evidence of future
    performance. No multiple-testing correction or broad market-regime
    robustness result is established in this audit.
12. **Critical test coverage:** There are 24 `tests/test_*.py` modules spanning
    core engines, integration, and import characterization. Representative
    named checks include `test_initial_values_are_none_until_history_is_sufficient`,
    `test_forward_targets_have_separate_feature_and_target_timestamps`,
    `test_temporal_split_is_ordered_and_purges_overlapping_labels`,
    `test_commission_and_slippage_reduce_equity_and_are_recorded`,
    `test_unapproved_planner_tool_is_blocked_before_any_execution`, and
    `test_reporting_tool_rejects_unsafe_paths`. Coverage is broad at the file
    level, but no coverage percentage or successful suite run is available.

## Verification results

| Check | Result | Details |
|---|---|---|
| Full test suite (`python -m pytest`) | BLOCKED | Windows Application Control prevented starting `python.exe`; pytest did not run. |
| Full test suite via `py -3.12 -m pytest` | BLOCKED | Python 3.12 executable was blocked by the same policy; pytest did not run. |
| Python compilation (`python -m compileall ...`) | BLOCKED | The interpreter could not start, so compilation was not performed. |
| Import characterization (`python -m pytest tests\\test_import_characterization.py -q`) | BLOCKED | The interpreter could not start; import side effects were not dynamically verified. |
| Manifest, README, architecture, plan, CI and ignore rules | REVIEWED | Static inspection completed. CI is configured to run pytest on Python 3.12. |
| Git worktree | CLEAN before this report | No product-code modifications were made during the audit. |

There are no reported test failures because pytest never started. Do not treat
that as a passing suite. The next acceptance step is to run the CI test command
in an environment where Python is permitted, then update the phase status based
on the actual result.

## Open risks and pending work

- **Release verification:** all runtime confidence is limited until pytest,
  compilation, and import characterization pass in CI or an allowed local
  environment.
- **Portfolio-level risk:** the integrated multi-asset flow combines equal
  capital sleeves on common timestamps; portfolio-wide drawdown and risk
  accounting are limited, as documented in the Master Plan.
- **OOS evidence:** walk-forward primitives are not integrated into the main
  research CLI/agent; present results as historical analysis, not validated
  out-of-sample strategy performance.
- **Callback trust:** walk-forward train/test separation is structural, but
  caller-provided evaluation callbacks can still introduce leakage if written
  incorrectly.
- **Filesystem scope:** `ResearchAgentRequest` rejects relative paths,
  traversal, filesystem roots, and symlinks, but permits any other absolute
  `data_directory` and `output_directory`. If requests can originate from
  untrusted callers, constrain these paths to application-configured roots.
- **Exception classification:** the broad catch around market-data loading in
  `run_strategy_research` can obscure an internal exception's category.
- **Unexplained tracked artifact:** review the purpose/provenance of
  `Usuarios.lnk`; it was left untouched.
- **Not implemented:** a general UI/API and deep-learning models remain outside
  the current implementation.
- **Explicitly blocked:** real broker connectivity and live order submission.

## Dependency additions during the roadmap

| Dependency | Introduced | Purpose |
|---|---|---|
| `yfinance>=0.2.54` | Market Data Engine | Yahoo Finance market-data provider |
| `scipy>=1.11` | Portfolio phase | Numerical optimization for maximum Sharpe |
| `hmmlearn>=0.3.2` | HMM/fundamental/universe phase | Gaussian HMM regime implementation |
| `vaderSentiment>=3.3.2` | Sentiment/ML phase | VADER sentiment scoring |
| `xgboost>=2.1` | Sentiment/ML phase | XGBoost classifier |
| `pytest>=8.0` | Initial project setup, development extra | Test runner |

No dependency was added for LangGraph, a real broker, or a news API.
