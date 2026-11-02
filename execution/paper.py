"""Deterministic in-memory paper broker with no network or credential support."""

from collections.abc import Mapping
import math
from numbers import Real

from backtest.costs import calculate_execution_cost
from backtest.types import BacktestConfig
from execution.account import AccountState, Position
from execution.orders import OrderExecution
from execution.types import Order, OrderSide, OrderStatus


class PaperBroker:
    """Execute market orders immediately at an explicitly supplied price."""

    def __init__(
        self,
        initial_cash: float = 100_000.0,
        commission_bps: float = 0.0,
        slippage_bps: float = 0.0,
    ) -> None:
        self._config = BacktestConfig(
            initial_cash=initial_cash,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
        )
        self._cash = self._config.initial_cash
        self._positions: dict[str, Position] = {}
        self._order_history: list[OrderExecution] = []
        self._order_ids: set[str] = set()

    @property
    def account_state(self) -> AccountState:
        positions = dict(self._positions)
        equity = self._cash + math.fsum(
            position.market_value for position in positions.values()
        )
        return AccountState(cash=self._cash, positions=positions, equity=equity)

    @property
    def order_history(self) -> tuple[OrderExecution, ...]:
        return tuple(self._order_history)

    def submit_order(self, order: Order, market_price: float) -> OrderExecution:
        if order.order_id in self._order_ids:
            return self._record(
                OrderExecution(
                    order=order,
                    status=OrderStatus.REJECTED,
                    status_history=(OrderStatus.CREATED, OrderStatus.REJECTED),
                    rejection_reason="Duplicate order_id.",
                )
            )
        self._order_ids.add(order.order_id)
        if (
            isinstance(market_price, bool)
            or not isinstance(market_price, Real)
            or not math.isfinite(market_price)
            or market_price <= 0
        ):
            return self._record(
                OrderExecution(
                    order=order,
                    status=OrderStatus.REJECTED,
                    status_history=(OrderStatus.CREATED, OrderStatus.REJECTED),
                    rejection_reason="market_price must be finite and positive.",
                )
            )

        current_position = self._positions.get(order.symbol)
        if order.side is OrderSide.SELL and (
            current_position is None or order.quantity > current_position.quantity
        ):
            return self._record(
                OrderExecution(
                    order=order,
                    status=OrderStatus.REJECTED,
                    status_history=(OrderStatus.CREATED, OrderStatus.REJECTED),
                    rejection_reason="Sell quantity exceeds the current position.",
                )
            )

        try:
            costs = calculate_execution_cost(
                market_price,
                order.quantity,
                order.side.value,
                self._config,
            )
        except ValueError as exc:
            return self._record(
                OrderExecution(
                    order=order,
                    status=OrderStatus.REJECTED,
                    status_history=(OrderStatus.CREATED, OrderStatus.REJECTED),
                    rejection_reason=str(exc),
                )
            )

        notional = costs.fill_price * order.quantity
        cash_delta = (
            notional + costs.commission
            if order.side is OrderSide.BUY
            else -(notional - costs.commission)
        )
        if order.side is OrderSide.BUY and cash_delta > self._cash:
            return self._record(
                OrderExecution(
                    order=order,
                    status=OrderStatus.REJECTED,
                    status_history=(OrderStatus.CREATED, OrderStatus.REJECTED),
                    rejection_reason="Insufficient funds.",
                )
            )

        updated_cash = self._cash - cash_delta
        updated_positions = dict(self._positions)
        if order.side is OrderSide.BUY:
            previous_quantity = (
                current_position.quantity if current_position is not None else 0.0
            )
            total_quantity = previous_quantity + order.quantity
            previous_cost = (
                current_position.average_price * previous_quantity
                if current_position is not None
                else 0.0
            )
            average_price = (previous_cost + notional) / total_quantity
            updated_positions[order.symbol] = Position(
                symbol=order.symbol,
                quantity=total_quantity,
                average_price=average_price,
                market_price=market_price,
            )
        else:
            assert current_position is not None
            remaining_quantity = current_position.quantity - order.quantity
            if remaining_quantity <= 1e-12:
                updated_positions.pop(order.symbol)
            else:
                updated_positions[order.symbol] = Position(
                    symbol=order.symbol,
                    quantity=remaining_quantity,
                    average_price=current_position.average_price,
                    market_price=market_price,
                )

        if not math.isfinite(updated_cash) or updated_cash < 0:
            return self._record(
                OrderExecution(
                    order=order,
                    status=OrderStatus.REJECTED,
                    status_history=(OrderStatus.CREATED, OrderStatus.REJECTED),
                    rejection_reason="Execution would produce invalid account cash.",
                )
            )
        self._cash = updated_cash
        self._positions = updated_positions
        return self._record(
            OrderExecution(
                order=order,
                status=OrderStatus.FILLED,
                status_history=(
                    OrderStatus.CREATED,
                    OrderStatus.ACCEPTED,
                    OrderStatus.FILLED,
                ),
                fill_price=costs.fill_price,
                commission=costs.commission,
                slippage=costs.slippage,
            )
        )

    def mark_to_market(self, prices: Mapping[str, float]) -> AccountState:
        """Update marks using explicit caller-supplied prices; never fetches data."""
        updated: dict[str, Position] = {}
        for symbol, position in self._positions.items():
            price = prices.get(symbol)
            if price is None:
                updated[symbol] = position
                continue
            if (
                isinstance(price, bool)
                or not isinstance(price, Real)
                or not math.isfinite(price)
                or price <= 0
            ):
                raise ValueError(f"Mark price for {symbol} must be finite and positive.")
            updated[symbol] = Position(
                symbol=symbol,
                quantity=position.quantity,
                average_price=position.average_price,
                market_price=price,
            )
        try:
            equity = self._cash + math.fsum(
                position.market_value for position in updated.values()
            )
        except OverflowError as exc:
            raise ValueError("Mark prices produce non-finite account equity.") from exc
        if not math.isfinite(equity):
            raise ValueError("Mark prices produce non-finite account equity.")
        self._positions = updated
        return AccountState(cash=self._cash, positions=updated, equity=equity)

    def _record(self, execution: OrderExecution) -> OrderExecution:
        self._order_history.append(execution)
        return execution
