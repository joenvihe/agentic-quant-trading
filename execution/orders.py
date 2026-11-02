"""Order submission and execution result values."""

from dataclasses import dataclass

from execution.types import Order, OrderStatus


@dataclass(frozen=True)
class OrderExecution:
    order: Order
    status: OrderStatus
    status_history: tuple[OrderStatus, ...]
    fill_price: float | None = None
    commission: float = 0.0
    slippage: float = 0.0
    rejection_reason: str | None = None

    @property
    def order_id(self) -> str:
        return self.order.order_id
