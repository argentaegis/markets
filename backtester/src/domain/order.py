"""Order — trading intent. Strategy produces Orders; Broker produces Fills.

Frozen so orders cannot be mutated after creation; safe for audit log and replay.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Order:
    """Immutable order: id, ts, symbol/contract_id, side, qty, order_type, limit_price, tif.

    Reasoning: instrument_id unifies underlying (symbol) and option (contract_id).
    tif supports GTC/IOC for future fill-model flexibility.
    trailing_stop_ticks: when set, backtester attaches broker-managed trailing stop (Plan 150).
    """

    id: str
    ts: datetime
    instrument_id: str  # contract_id for options, symbol for underlying
    side: str  # "BUY" | "SELL"
    qty: int
    order_type: str  # "market" | "limit" | "stop"
    limit_price: float | None = None
    tif: str = "GTC"  # GTC, IOC, etc.
    trailing_stop_ticks: int | None = None
