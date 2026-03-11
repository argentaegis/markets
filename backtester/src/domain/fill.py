"""Fill — execution reality. Broker produces Fills from Orders via FillModel.

Portfolio updates only from fills (never from Orders). order_id links fill back to
Order for audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Fill:
    """Fill from order execution: order_id, ts, fill_price, fill_qty, fees, liquidity_flag.

    Reasoning: fill_price/fill_qty drive P&L and position updates. liquidity_flag
    for maker/taker (future cost modeling).
    """

    order_id: str
    ts: datetime
    fill_price: float
    fill_qty: int
    fees: float = 0.0
    liquidity_flag: str | None = None
