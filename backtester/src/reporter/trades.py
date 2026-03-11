"""Trade ledger — FIFO matching of fills into round-trip trades.

Reasoning: a Trade pairs an opening fill with its closing fill for the same
instrument. FIFO matching is the standard accounting convention. Open positions
(no closing fill yet) do NOT produce a Trade — they appear only in
final_portfolio. This enables clean win/loss analysis and trades.csv output.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from src.domain.fill import Fill
from src.domain.order import Order


@dataclass
class Trade:
    """Round-trip trade derived from fills via FIFO matching, or open position marked at end.

    Reasoning: entry/exit prices and timestamps enable P&L calculation and
    trade-level analysis. multiplier defaults to 100 (options contracts).
    is_open=True for positions emitted via open_marks (no closing fill).
    """

    instrument_id: str
    side: str  # "LONG" or "SHORT" (direction of opening leg)
    qty: int
    entry_ts: datetime
    entry_price: float
    exit_ts: datetime
    exit_price: float
    realized_pnl: float
    fees: float
    multiplier: float
    is_open: bool = False  # True when position was never closed (marked at end for reporting)


@dataclass
class _OpenLot:
    """Internal FIFO lot tracker for position building."""

    ts: datetime
    price: float
    qty: int
    fees: float


def derive_trades(
    fills: list[Fill],
    orders: list[Order],
    *,
    multiplier: float = 100.0,
    open_marks: dict[str, tuple[float, datetime]] | None = None,
    instrument_multipliers: dict[str, float] | None = None,
) -> list[Trade]:
    """Walk fills in timestamp order, FIFO-match into closed Trades.

    Reasoning: orders are needed to determine instrument_id and side for each fill.
    Fills that open a position push onto a per-instrument deque. Fills that close
    a position pop from the front (FIFO) and emit Trades.

    When open_marks is provided, remaining open positions are emitted as trades
    marked to the given price at the given timestamp. This ensures buy-and-hold
    strategies and any other open positions appear in trades.csv.

    instrument_multipliers overrides the default multiplier for specific
    instruments (e.g. equity uses 1.0, options use 100.0).
    """
    order_map: dict[str, Order] = {o.id: o for o in orders}
    sorted_fills = sorted(fills, key=lambda f: f.ts)

    def _mult(instrument_id: str) -> float:
        if instrument_multipliers and instrument_id in instrument_multipliers:
            return instrument_multipliers[instrument_id]
        return multiplier

    # Per-instrument open lots: instrument_id → (direction, lots)
    open_lots: dict[str, tuple[str, list[_OpenLot]]] = {}
    trades: list[Trade] = []

    for fill in sorted_fills:
        order = order_map[fill.order_id]
        instrument = order.instrument_id
        side = order.side  # "BUY" or "SELL"

        if instrument not in open_lots:
            # First fill for this instrument — opens a position.
            direction = "LONG" if side == "BUY" else "SHORT"
            open_lots[instrument] = (direction, [_OpenLot(fill.ts, fill.fill_price, fill.fill_qty, fill.fees)])
            continue

        direction, lots = open_lots[instrument]
        is_closing = (direction == "LONG" and side == "SELL") or (direction == "SHORT" and side == "BUY")

        if is_closing:
            _match_fifo(instrument, direction, lots, fill, trades, _mult(instrument))
            if not lots:
                del open_lots[instrument]
        else:
            # Adding to existing position in same direction.
            lots.append(_OpenLot(fill.ts, fill.fill_price, fill.fill_qty, fill.fees))

    if open_marks:
        _emit_open_trades(open_lots, open_marks, trades, multiplier, instrument_multipliers)

    return trades


def _emit_open_trades(
    open_lots: dict[str, tuple[str, list[_OpenLot]]],
    open_marks: dict[str, tuple[float, datetime]],
    trades: list[Trade],
    default_multiplier: float,
    instrument_multipliers: dict[str, float] | None = None,
) -> None:
    """Emit trades for remaining open positions using mark prices.

    Reasoning: open positions at run end should appear in trades.csv so the
    user can see unrealized P&L. Exit price is the final mark; exit_ts is
    the last timestamp.
    """
    for instrument, (direction, lots) in open_lots.items():
        mark_entry = open_marks.get(instrument)
        if mark_entry is None:
            continue
        mark_price, mark_ts = mark_entry
        mult = (instrument_multipliers or {}).get(instrument, default_multiplier)
        for lot in lots:
            if lot.qty <= 0:
                continue
            if direction == "LONG":
                pnl = (mark_price - lot.price) * lot.qty * mult
            else:
                pnl = (lot.price - mark_price) * lot.qty * mult
            trades.append(
                Trade(
                    instrument_id=instrument,
                    side=direction,
                    qty=lot.qty,
                    entry_ts=lot.ts,
                    entry_price=lot.price,
                    exit_ts=mark_ts,
                    exit_price=mark_price,
                    realized_pnl=pnl,
                    fees=lot.fees,
                    multiplier=mult,
                    is_open=True,
                )
            )


def _match_fifo(
    instrument: str,
    direction: str,
    lots: list[_OpenLot],
    closing_fill: Fill,
    trades: list[Trade],
    multiplier: float,
) -> None:
    """Pop lots FIFO to match closing fill quantity, emitting Trades.

    Reasoning: a single closing fill may consume multiple opening lots
    (partial fills). Each matched pair becomes one Trade.
    """
    remaining = closing_fill.fill_qty
    closing_fee_per_unit = closing_fill.fees / closing_fill.fill_qty if closing_fill.fill_qty else 0.0

    while remaining > 0 and lots:
        lot = lots[0]
        matched_qty = min(lot.qty, remaining)

        entry_fee = (lot.fees / lot.qty) * matched_qty if lot.qty else 0.0
        exit_fee = closing_fee_per_unit * matched_qty

        if direction == "LONG":
            pnl = (closing_fill.fill_price - lot.price) * matched_qty * multiplier
        else:
            pnl = (lot.price - closing_fill.fill_price) * matched_qty * multiplier

        trades.append(
            Trade(
                instrument_id=instrument,
                side=direction,
                qty=matched_qty,
                entry_ts=lot.ts,
                entry_price=lot.price,
                exit_ts=closing_fill.ts,
                exit_price=closing_fill.fill_price,
                realized_pnl=pnl,
                fees=entry_fee + exit_fee,
                multiplier=multiplier,
            )
        )

        lot.qty -= matched_qty
        remaining -= matched_qty
        if lot.qty == 0:
            lots.pop(0)
