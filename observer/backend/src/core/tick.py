"""Tick normalization utilities — normalize_price, ticks_between.

Uses Decimal internally for exact arithmetic (avoids floating-point rounding
errors when dividing by tick_size), but accepts and returns float to match the
domain type convention. Critical for futures with small tick sizes (ES 0.25,
CL 0.01) where float division can produce off-by-one-tick errors.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal


def normalize_price(price: float, tick_size: float) -> float:
    """Round price to the nearest tick.

    Reasoning: Strategies and UI must display prices on valid tick boundaries.
    Decimal arithmetic prevents float rounding errors (e.g. 5412.30 / 0.25).
    """
    d_price = Decimal(str(price))
    d_tick = Decimal(str(tick_size))
    ticks = (d_price / d_tick).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
    return float(ticks * d_tick)


def ticks_between(price_a: float, price_b: float, tick_size: float) -> int:
    """Number of ticks from price_a to price_b (signed).

    Reasoning: Risk calculations (R-multiples) and stop distances need exact
    tick counts. Decimal prevents float drift on division.
    """
    d_a = Decimal(str(price_a))
    d_b = Decimal(str(price_b))
    d_tick = Decimal(str(tick_size))
    return int((d_b - d_a) / d_tick)
