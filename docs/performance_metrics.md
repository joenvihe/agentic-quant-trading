# Performance Metrics

The evaluator consumes a `BacktestResult` and returns `PerformanceMetrics`.
Defaults assume daily observations (`periods_per_year=252`) and a zero annual
risk-free rate. Both `periods_per_year` and `risk_free_rate` can be passed to
`evaluation.calculate_metrics`.

## Definitions

- **Total Return:** `final_equity / initial_cash - 1`.
- **CAGR:** `(final_equity / initial_cash) ** (periods_per_year / periods) - 1`,
  where `periods` is the number of equity-curve intervals. It is `None` when
  there are no intervals or ending capital is not positive.
- **Annualized Volatility:** population standard deviation of period equity
  returns multiplied by `sqrt(periods_per_year)`. It is `None` with fewer than
  two observations or zero/non-finite deviation.
- **Sharpe:** mean period excess return divided by population standard
  deviation of period excess returns, multiplied by `sqrt(periods_per_year)`.
  The annual risk-free rate is converted to a per-period rate by division.
  Undefined/zero deviation produces `None`.
- **Sortino:** mean period excess return divided by the root-mean-square
  downside excess return, multiplied by `sqrt(periods_per_year)`. It is `None`
  when the downside deviation is zero or undefined.
- **Maximum Drawdown:** the minimum peak-to-trough equity decline, with initial
  cash included as the starting peak. It is reported as a non-positive
  fraction; an empty curve yields `None`.
- **Calmar:** CAGR divided by the absolute maximum drawdown. It is `None` when
  CAGR is unavailable or maximum drawdown is zero.
- **Win Rate:** profitable realized sell events divided by all sell events
  that close a position, using average-cost basis inclusive of buy/sell
  commissions. Open positions are not counted as wins/losses.
- **Profit Factor:** total positive realized PnL divided by the absolute total
  negative realized PnL, using the same average-cost convention. It is `None`
  when there is no realized loss (including no closed trades), rather than
  infinity.
- **Number of Trades:** number of executed fills (each buy or sell fill counts
  separately).

Any undefined or non-finite scalar metric is returned as `None`; zero
denominators are checked rather than hidden.

## Causal execution and costs

A `TargetPosition` timestamp denotes a decision made using information through
that bar's close. The backtest applies it at the next bar's open. Quantity is
sized from equity and closing price available at the decision timestamp; gaps
may therefore make the requested weight unattainable, in which case buys are
capped by available cash.

Slippage is an adverse price adjustment in basis points: buys fill above the
open and sells below it. The `Trade.slippage` field reports the resulting
currency cost; this cost is already reflected in fill price and is not charged a
second time. Commission is a separate basis-point charge on executed notional.
Positions are not force-liquidated at the end of the data.

The Buy and Hold benchmark submits a full-exposure target at the first bar's
close and consequently enters at the next bar's open, following the same
causality convention as strategy positions. It is not a live-trading adapter.

## Temporal walk-forward evaluation

`evaluation.generate_time_splits` uses bar counts to produce expanding or
rolling windows. It validates ordered, unique, timezone-aware timestamps and
requires strict separation between the final train timestamp and first test
timestamp. Data is never shuffled.

`evaluation.run_walk_forward` passes only the train slice to candidate
evaluations, selects the candidate with the highest configured finite metric,
then passes only the test slice and selected parameters to the out-of-sample
evaluation. Selection maximizes by default; `maximize_metric=False` selects
the minimum instead. The callback must generate any decisions using only the
slice it receives. A test slice does not include train-period warm-up
observations.
`evaluation.summarize_robustness` aggregates valid out-of-sample returns across
folds and retains fold warnings.

## Risk decisions

`risk.evaluate_risk` is independent of strategy selection and execution.
`RiskLimits` caps per-asset weight and total portfolio exposure; when
`target_volatility` is configured, exposure is scaled by target volatility
divided by current annualized realized volatility, capped at the requested
weight. Missing/invalid realized volatility fails closed to zero exposure when
targeting is enabled. The optional drawdown circuit breaker blocks exposure
when positive-fraction drawdown is at or above `max_drawdown`.

`risk.calculate_realized_volatility` estimates annualized volatility from
finite, positive closing prices and log returns; it returns `None` when there
are fewer than three closes. The caller must pass the estimate that was
available at the strategy decision timestamp. The Risk Engine returns an
explicit decision and reason codes; it does not alter prices or send orders.

## Scope and limitations

This implementation supports one asset, daily bars, long-only exposure from
zero to one, and no leverage or short selling. It does not model taxes,
dividends/corporate actions, order-book liquidity, partial fills, financing,
or intraday execution. Walk-forward evaluation does not include training bars
as warm-up context for its test windows. Portfolio aggregation is not
implemented.
