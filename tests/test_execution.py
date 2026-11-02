from datetime import datetime, timezone

import pytest

from execution import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    PaperBroker,
)


SUBMITTED_AT = datetime(2025, 1, 2, tzinfo=timezone.utc)


def order(
    order_id: str,
    side: OrderSide,
    quantity: float,
    symbol: str = "SPY",
) -> Order:
    return Order(
        order_id=order_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        order_type=OrderType.MARKET,
        submitted_at=SUBMITTED_AT,
    )


def test_market_buy_and_sell_update_account_positions() -> None:
    broker = PaperBroker(initial_cash=10_000)

    buy = broker.submit_order(order("buy-1", OrderSide.BUY, 10), 100)
    bought_account = broker.account_state
    sell = broker.submit_order(order("sell-1", OrderSide.SELL, 4), 110)
    final_account = broker.account_state

    assert buy.status is OrderStatus.FILLED
    assert buy.status_history == (
        OrderStatus.CREATED,
        OrderStatus.ACCEPTED,
        OrderStatus.FILLED,
    )
    assert bought_account.cash == 9_000
    assert bought_account.positions["SPY"].quantity == 10
    assert bought_account.equity == 10_000
    assert sell.status is OrderStatus.FILLED
    assert final_account.positions["SPY"].quantity == 6
    assert final_account.cash == 9_440
    assert final_account.equity == 10_100


def test_insufficient_funds_and_overselling_are_rejected_without_state_change() -> None:
    broker = PaperBroker(initial_cash=500)

    unaffordable = broker.submit_order(order("buy-large", OrderSide.BUY, 6), 100)
    broker.submit_order(order("buy-small", OrderSide.BUY, 2), 100)
    before_oversell = broker.account_state
    oversell = broker.submit_order(order("sell-too-many", OrderSide.SELL, 3), 100)
    sell_empty = broker.submit_order(order("sell-empty", OrderSide.SELL, 1), 100)

    assert unaffordable.status is OrderStatus.REJECTED
    assert "Insufficient funds" in (unaffordable.rejection_reason or "")
    assert oversell.status is OrderStatus.REJECTED
    assert "exceeds" in (oversell.rejection_reason or "")
    assert sell_empty.status is OrderStatus.REJECTED
    assert broker.account_state == before_oversell


def test_commission_and_adverse_slippage_are_applied() -> None:
    broker = PaperBroker(
        initial_cash=10_000,
        commission_bps=10,
        slippage_bps=20,
    )

    execution = broker.submit_order(order("buy-costed", OrderSide.BUY, 10), 100)

    assert execution.status is OrderStatus.FILLED
    assert execution.fill_price == pytest.approx(100.2)
    assert execution.slippage == pytest.approx(2.0)
    assert execution.commission == pytest.approx(1.002)
    assert broker.account_state.cash == pytest.approx(8_996.998)
    assert broker.account_state.equity == pytest.approx(9_996.998)

    sell = broker.submit_order(order("sell-costed", OrderSide.SELL, 10), 100)
    assert sell.status is OrderStatus.FILLED
    assert sell.fill_price == pytest.approx(99.8)
    assert sell.slippage == pytest.approx(2.0)
    assert sell.commission == pytest.approx(0.998)
    assert broker.account_state.positions == {}


def test_invalid_order_values_and_market_prices_are_rejected() -> None:
    with pytest.raises(ValueError, match="quantity"):
        order("zero", OrderSide.BUY, 0)
    with pytest.raises(ValueError, match="symbol"):
        order("empty-symbol", OrderSide.BUY, 1, " ")

    broker = PaperBroker(initial_cash=1000)
    execution = broker.submit_order(order("bad-price", OrderSide.BUY, 1), float("nan"))

    assert execution.status is OrderStatus.REJECTED
    assert "market_price" in (execution.rejection_reason or "")
    assert broker.account_state.cash == 1000


def test_mark_to_market_updates_equity_from_explicit_prices() -> None:
    broker = PaperBroker(initial_cash=1000)
    broker.submit_order(order("buy", OrderSide.BUY, 2), 100)

    account = broker.mark_to_market({"SPY": 125})

    assert account.cash == 800
    assert account.positions["SPY"].market_price == 125
    assert account.positions["SPY"].market_value == 250
    assert account.equity == 1050
    with pytest.raises(ValueError, match="finite and positive"):
        broker.mark_to_market({"SPY": 0})
    assert broker.account_state == account


def test_execution_is_deterministic_and_duplicate_order_ids_are_rejected() -> None:
    first = PaperBroker(initial_cash=2000, commission_bps=3, slippage_bps=5)
    second = PaperBroker(initial_cash=2000, commission_bps=3, slippage_bps=5)
    request = order("same-id", OrderSide.BUY, 3)

    first_result = first.submit_order(request, 101.25)
    second_result = second.submit_order(request, 101.25)

    assert first_result == second_result
    assert first.account_state == second.account_state
    duplicate = first.submit_order(request, 101.25)
    assert duplicate.status is OrderStatus.REJECTED
    assert "Duplicate" in (duplicate.rejection_reason or "")
    assert len(first.account_state.positions) == 1
