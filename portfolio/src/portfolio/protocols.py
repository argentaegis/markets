"""Protocols: FillLike, OrderLike. Consumers pass their existing types; no adapter needed."""

from __future__ import annotations

from typing import Protocol


class FillLike(Protocol):
    """Fill attributes required by apply_fill. Backtester Fill satisfies this."""

    fill_price: float
    fill_qty: int
    fees: float


class OrderLike(Protocol):
    """Order attributes required by apply_fill. Backtester Order satisfies this."""

    instrument_id: str
    side: str  # "BUY" | "SELL"
