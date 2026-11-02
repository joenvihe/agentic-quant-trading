"""Buy-and-hold benchmark using the same causal next-bar execution model."""

from backtest.engine import run_backtest
from backtest.types import BacktestConfig, BacktestResult
from data.market_data import MarketData
from strategies.types import TargetPosition


def buy_and_hold_benchmark(
    market_data: MarketData,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    if not market_data.bars:
        raise ValueError("Market data history cannot be empty.")
    first_bar = market_data.bars[0]
    target = TargetPosition(
        symbol=market_data.ticker,
        timestamp=first_bar.timestamp,
        weight=1.0,
        reason="buy_and_hold",
    )
    return run_backtest(
        market_data,
        (target,),
        strategy_name="buy_and_hold",
        config=config,
    )
