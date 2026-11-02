# Application tools

The `application.tools` package exposes typed adapters over existing domain
services. Tools return a `ToolResponse` and do not implement quantitative
calculations, dynamically import user-selected code, invoke an LLM, or perform
real trading.

## Shared response contract

```python
@dataclass(frozen=True)
class ToolResponse:
    success: bool
    trace_id: str
    data: Mapping[str, Any]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
```

Tools generate a UUID trace ID unless the caller supplies a safe 1-128
character identifier containing only letters, digits, `.`, `_`, `:`, or `-`.
Invalid trace IDs are rejected and replaced by a generated ID in the error
response. Result data is restricted to JSON-compatible primitives,
dataclasses, mappings with string keys, sequences, dates/times, paths, and
finite numbers. Unsupported objects and non-finite numeric values are errors,
not silently stringified.

Requests are frozen dataclasses defined in their corresponding modules. Each
has an optional `trace_id`. Tool errors are returned in `errors`; domain
warnings and risk reductions are returned in `warnings`. A failed portfolio
optimization preserves its explicit domain result in `data` and reports the
failure in `errors`.

## Tools

| Module | Request and entry point | Domain behavior |
|---|---|---|
| `application.tools.research` | `ResearchRequest(symbol)` → `research_symbol(request, provider, settings)` | Calls `generate_research_report` with the explicitly injected `MarketDataProvider` and `Settings`. Provider/network access occurs only during the explicit call. |
| `application.tools.backtest` | `BacktestRequest(market_data, target_positions, strategy_name, config)` → `execute_backtest(request)` | Calls the existing causal backtest engine; decisions at a bar close execute no earlier than the next bar. |
| `application.tools.comparison` | `ComparisonRequest(results, periods_per_year, risk_free_rate)` → `compare_strategies(request)` | Uses existing performance metrics and comparison functions. Requires distinct strategy names and identical equity-curve timestamps; compares each result to the first result as the baseline. |
| `application.tools.risk` | `RiskRequest(requested_weight, current_exposure, limits, realized_volatility, current_drawdown)` → `evaluate_risk_request(request)` | Calls the existing pure Risk Engine. Approved weight and reason codes are returned; no order is submitted. |
| `application.tools.portfolio` | `PortfolioRequest(symbols, returns_by_symbol, constraints, periods_per_year, risk_free_rate)` → `optimize_portfolio(request)` | Calls `MaximumSharpeOptimizer`. Optimization failure remains explicit; the tool never substitutes another allocation. |
| `application.tools.reporting` | `ReportingRequest(backtest_result, metrics, benchmark_comparison, formats, subdirectory, …)` → `generate_report(request, output_root=...)` | Builds a report from already-calculated results and calls the existing JSON, CSV, and/or HTML writer. It does not recalculate strategy decisions or metrics. |

## Filesystem boundary

The report tool receives `output_root` from trusted application configuration,
not from report content. It generates filenames itself and permits only an
optional single subdirectory made from ASCII letters, digits, `_`, and `-`.
Traversal, absolute paths, drive names, separators, and resolved destinations
outside the configured root are rejected. Existing and symlink report targets
are not overwritten. Configure the root deliberately; report generation writes
files only when explicitly invoked.

## Safety and integration

Market-data providers are dependencies injected by the application, not values
decoded from a request. No tool accepts source code, import paths, shell
commands, agent instructions, or arbitrary callables. PaperBroker is not
connected to any tool. Nothing in this package configures logging, downloads
data, or writes files at import time.

Examples and integration tests use fake providers and synthetic market data.
The research tool requires a provider explicitly, so a caller opts into any
external data access by choosing and invoking that provider.
