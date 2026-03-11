"""Tick normalization utilities — normalize_price, ticks_between.

Uses Decimal internally for exact arithmetic. No observer dependency (S1).
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal


def normalize_price(price: float, tick_size: float) -> float:
    """Round price to the nearest tick."""
    d_price = Decimal(str(price))
    d_tick = Decimal(str(tick_size))
    ticks = (d_price / d_tick).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
    return float(ticks * d_tick)


def ticks_between(price_a: float, price_b: float, tick_size: float) -> int:
    """Number of ticks from price_a to price_b (signed)."""
    d_a = Decimal(str(price_a))
    d_b = Decimal(str(price_b))
    d_tick = Decimal(str(tick_size))
    return int((d_b - d_a) / d_tick)
