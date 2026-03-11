"""Tick normalization — normalize_price.

Uses Decimal internally for exact arithmetic (avoids float drift when
dividing by tick_size). Same algo as observer/strategizer. Critical for
futures (ES 0.25, CL 0.01) where float rounding can produce off-tick fills.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal


def normalize_price(price: float, tick_size: float) -> float:
    """Round price to the nearest tick.

    Uses ROUND_HALF_EVEN (banker's rounding) for determinism.
    """
    d_price = Decimal(str(price))
    d_tick = Decimal(str(tick_size))
    ticks = (d_price / d_tick).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
    return float(ticks * d_tick)
