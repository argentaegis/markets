"""FillModel: quote-based and synthetic spread fills.

Conforms to 000 M5. BUY at ask, SELL at bid when quotes available;
synthetic spread around mid when bid/ask absent.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.fill import Fill
from src.domain.order import Order
from src.domain.quotes import Quote
from src.domain.snapshot import MarketSnapshot

from src.domain.futures import FuturesContractSpec


@dataclass
class FillModelConfig:
    """Fill model configuration. synthetic_spread_bps used when only mid available."""

    synthetic_spread_bps: float = 50.0


def _apply_synthetic_spread(mid: float, side: str, spread_bps: float) -> float:
    """Apply synthetic spread: BUY at mid+half_spread, SELL at mid-half_spread."""
    half_spread = mid * (spread_bps / 10000) / 2
    return mid + half_spread if side == "BUY" else mid - half_spread


def fill_order(
    order: Order,
    snapshot: MarketSnapshot,
    *,
    symbol: str = "",
    fill_config: FillModelConfig | None = None,
    futures_spec: FuturesContractSpec | None = None,
    use_open: bool = False,
) -> Fill | None:
    """Produce fill from order and snapshot. Returns None when price unavailable.

    Quote-based: BUY at ask, SELL at bid when bid != ask.
    Synthetic: mid +/- spread/2 when bid==ask (mid-only) or when filling underlying from bar.
    use_open: when True, use bar.open instead of bar.close for underlying/equity (Plan 265).
    Stop orders: fill when bar high/low crosses stop level (110).
    When futures_spec provided, tick-aligns fill_price before returning (090).
    """
    config = fill_config or FillModelConfig()
    instrument_id = order.instrument_id

    fill_price: float | None = None

    # Stop order: fill when bar crosses stop level (110)
    if (
        order.order_type == "stop"
        and order.limit_price is not None
        and instrument_id == symbol
        and snapshot.underlying_bar is not None
    ):
        bar = snapshot.underlying_bar
        stop = order.limit_price
        if order.side == "BUY" and bar.high >= stop:
            fill_price = stop if bar.low <= stop else bar.open
        elif order.side == "SELL" and bar.low <= stop:
            fill_price = stop if bar.high >= stop else bar.open
        else:
            fill_price = None

    # Underlying: use bar open or close as mid with synthetic spread (market/limit)
    # Plan 265: use_open=True for next-bar-open fill timing
    elif snapshot.underlying_bars_by_symbol is not None:
        bar = snapshot.underlying_bars_by_symbol.get(instrument_id)
        if bar is not None:
            mid = bar.open if use_open else bar.close
            fill_price = _apply_synthetic_spread(mid, order.side, config.synthetic_spread_bps)
    elif instrument_id == symbol and snapshot.underlying_bar is not None:
        bar = snapshot.underlying_bar
        mid = bar.open if use_open else bar.close
        fill_price = _apply_synthetic_spread(mid, order.side, config.synthetic_spread_bps)

    elif snapshot.option_quotes is not None:
        q = snapshot.option_quotes.quotes.get(instrument_id)
        if isinstance(q, Quote):
            if q.bid != q.ask:
                fill_price = q.ask if order.side == "BUY" else q.bid
            else:
                mid = q.mid if q.mid is not None else q.bid
                fill_price = _apply_synthetic_spread(mid, order.side, config.synthetic_spread_bps)

    if fill_price is None:
        return None

    if futures_spec is not None:
        from src.utils.tick import normalize_price

        fill_price = normalize_price(fill_price, futures_spec.tick_size)

    return Fill(
        order_id=order.id,
        ts=snapshot.ts,
        fill_price=fill_price,
        fill_qty=order.qty,
        fees=0.0,
    )
