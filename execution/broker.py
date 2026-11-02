"""Broker protocol for explicit-price, synchronous paper order execution."""

from typing import Protocol

from execution.account import AccountState
from execution.orders import OrderExecution
from execution.types import Order


class Broker(Protocol):
    def submit_order(self, order: Order, market_price: float) -> OrderExecution:
        """Submit and resolve an order using the caller-provided price only."""

    @property
    def account_state(self) -> AccountState:
        """Return the latest cash, marked positions and total equity."""

    @property
    def order_history(self) -> tuple[OrderExecution, ...]:
        """Return immutable order execution history."""
