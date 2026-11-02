"""Validated order values and lifecycle states."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import math
from numbers import Real


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    ACCEPTED = "ACCEPTED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class Order:
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType
    submitted_at: datetime
    limit_price: float | None = None

    def __post_init__(self) -> None:
        if not self.order_id.strip():
            raise ValueError("order_id cannot be empty.")
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty.")
        if not isinstance(self.side, OrderSide):
            raise ValueError("side must be an OrderSide.")
        if not isinstance(self.order_type, OrderType):
            raise ValueError("order_type must be an OrderType.")
        if (
            isinstance(self.quantity, bool)
            or not isinstance(self.quantity, Real)
            or not math.isfinite(self.quantity)
        ):
            raise ValueError("quantity must be finite and positive.")
        if self.quantity <= 0:
            raise ValueError("quantity must be finite and positive.")
        if (
            self.submitted_at.tzinfo is None
            or self.submitted_at.utcoffset() is None
        ):
            raise ValueError("submitted_at must be timezone-aware.")
        if self.order_type is OrderType.MARKET and self.limit_price is not None:
            raise ValueError("Market orders cannot have a limit_price.")
        if self.limit_price is not None and (
            isinstance(self.limit_price, bool)
            or not isinstance(self.limit_price, Real)
            or not math.isfinite(self.limit_price)
            or self.limit_price <= 0
        ):
            raise ValueError("limit_price must be finite and positive.")
        object.__setattr__(self, "order_id", self.order_id.strip())
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(
            self, "submitted_at", self.submitted_at.astimezone(timezone.utc)
        )
