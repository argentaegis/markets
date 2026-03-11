"""TrailingStopManager — broker-managed trailing stop exits (Plan 150).

Tracks per-instrument high-water (long) or low-water (short). Each step evaluates
bar OHLC; triggers when price moves against by N ticks. Returns synthetic (Fill, Order) pairs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.fill import Fill
from src.domain.order import Order
from src.domain.portfolio import PortfolioState
from src.domain.snapshot import MarketSnapshot
from src.utils.tick import normalize_price


@dataclass
class _TrailingState:
    """Per-instrument trailing stop state."""

    entry_ts: datetime
    water_mark: float | None  # None = not yet initialized from bar
    trailing_stop_ticks: int
    side: str  # "LONG" | "SHORT"


class TrailingStopManager:
    """Tracks positions with trailing stops; evaluates each step and returns synthetic exit fills."""

    def __init__(self) -> None:
        self._state: dict[str, _TrailingState] = {}

    def register_fill(self, fill: Fill, order: Order) -> None:
        """Register a fill from an order with trailing_stop_ticks. Adds/updates state."""
        if order.trailing_stop_ticks is None:
            return
        instrument_id = order.instrument_id
        side = "LONG" if order.side == "BUY" else "SHORT"
        self._state[instrument_id] = _TrailingState(
            entry_ts=fill.ts,
            water_mark=None,
            trailing_stop_ticks=order.trailing_stop_ticks,
            side=side,
        )

    def evaluate(
        self,
        portfolio: PortfolioState,
        snapshot: MarketSnapshot,
        tick_size_map: dict[str, float],
    ) -> list[tuple[Fill, Order]]:
        """Evaluate trailing stops. Returns synthetic (Fill, Order) pairs for triggered exits."""
        bar = _get_bar(snapshot)
        if bar is None:
            return []

        results: list[tuple[Fill, Order]] = []
        tick_default = 0.01

        for instrument_id in list(self._state.keys()):
            pos = portfolio.positions.get(instrument_id)
            if pos is None:
                del self._state[instrument_id]
                continue

            state = self._state[instrument_id]
            # Skip evaluation on entry bar: fill happened at bar close; bar's OHLC predates
            # our position. Trailing from the next bar onward.
            if snapshot.ts == state.entry_ts:
                continue

            tick_size = tick_size_map.get(instrument_id, tick_default)
            trigger_price: float | None = None

            if state.side == "LONG" and pos.qty > 0:
                # high_water = max(high_water, bar.high)
                hw = state.water_mark
                hw = bar.high if hw is None else max(hw, bar.high)
                state.water_mark = hw
                # Trigger when bar.low <= high_water - N*tick_size
                threshold = hw - state.trailing_stop_ticks * tick_size
                if bar.low <= threshold:
                    trigger_price = normalize_price(threshold, tick_size)
            elif state.side == "SHORT" and pos.qty < 0:
                # low_water = min(low_water, bar.low)
                lw = state.water_mark
                lw = bar.low if lw is None else min(lw, bar.low)
                state.water_mark = lw
                # Trigger when bar.high >= low_water + N*tick_size
                threshold = lw + state.trailing_stop_ticks * tick_size
                if bar.high >= threshold:
                    trigger_price = normalize_price(threshold, tick_size)
            else:
                # Position side doesn't match state (e.g. position flipped)
                del self._state[instrument_id]
                continue

            if trigger_price is not None:
                exit_side = "SELL" if pos.qty > 0 else "BUY"
                exit_qty = abs(pos.qty)
                oid = f"trailing-{instrument_id}-{snapshot.ts.isoformat()}"
                order = Order(
                    id=oid,
                    ts=snapshot.ts,
                    instrument_id=instrument_id,
                    side=exit_side,
                    qty=exit_qty,
                    order_type="market",
                    limit_price=None,
                    tif="GTC",
                    trailing_stop_ticks=None,
                )
                fill = Fill(
                    order_id=oid,
                    ts=snapshot.ts,
                    fill_price=trigger_price,
                    fill_qty=exit_qty,
                    fees=0.0,
                    liquidity_flag=None,
                )
                results.append((fill, order))
                del self._state[instrument_id]

        return results


def _get_bar(snapshot: MarketSnapshot):  # -> BarRow | None
    """Return current bar from snapshot. Futures use latest from futures_bars."""
    if snapshot.futures_bars and len(snapshot.futures_bars) > 0:
        return snapshot.futures_bars[-1]
    return snapshot.underlying_bar
