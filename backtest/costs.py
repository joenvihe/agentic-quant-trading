"""Transaction-cost and adverse-slippage calculations."""

from dataclasses import dataclass
import math

from backtest.types import BacktestConfig


@dataclass(frozen=True)
class ExecutionCost:
    fill_price: float
    commission: float
    slippage: float


def calculate_execution_cost(
    reference_price: float,
    quantity: float,
    side: str,
    config: BacktestConfig,
) -> ExecutionCost:
    if not math.isfinite(reference_price) or reference_price <= 0:
        raise ValueError("reference_price must be finite and positive.")
    if not math.isfinite(quantity) or quantity <= 0:
        raise ValueError("quantity must be finite and positive.")
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL.")

    slippage_rate = config.slippage_bps / 10_000
    direction = 1 if side == "BUY" else -1
    fill_price = reference_price * (1 + direction * slippage_rate)
    if not math.isfinite(fill_price) or fill_price <= 0:
        raise ValueError("Slippage results in a non-positive fill price.")
    slippage = abs(fill_price - reference_price) * quantity
    commission = fill_price * quantity * config.commission_bps / 10_000
    return ExecutionCost(
        fill_price=fill_price,
        commission=commission,
        slippage=slippage,
    )
