"""Trade ledger tests — Phase 1 of 080.

Reasoning: derive_trades pairs fills into open/close trades via FIFO matching.
Trade-level P&L enables win/loss analysis and trades.csv output.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.fill import Fill
from src.domain.order import Order
from src.reporter.trades import Trade, derive_trades


def _utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 2, hour, minute, tzinfo=timezone.utc)


def _order(oid: str, instrument: str, side: str, qty: int, ts: datetime | None = None) -> Order:
    return Order(id=oid, ts=ts or _utc(14, 31), instrument_id=instrument, side=side, qty=qty, order_type="market")


def _fill(oid: str, price: float, qty: int, ts: datetime | None = None, fees: float = 0.0) -> Fill:
    return Fill(order_id=oid, ts=ts or _utc(14, 31), fill_price=price, fill_qty=qty, fees=fees)


def test_trade_dataclass_fields() -> None:
    """Trade holds all required fields."""
    t = Trade(
        instrument_id="SPY|C|480",
        side="LONG",
        qty=1,
        entry_ts=_utc(14, 31),
        entry_price=5.30,
        exit_ts=_utc(14, 32),
        exit_price=5.50,
        realized_pnl=20.0,
        fees=2.30,
        multiplier=100.0,
    )
    assert t.instrument_id == "SPY|C|480"
    assert t.side == "LONG"
    assert t.realized_pnl == 20.0


def test_single_buy_sell_produces_one_trade() -> None:
    """Buy then sell on same instrument → 1 trade."""
    orders = [
        _order("b1", "SPY|C|480", "BUY", 1, _utc(14, 31)),
        _order("s1", "SPY|C|480", "SELL", 1, _utc(14, 32)),
    ]
    fills = [
        _fill("b1", 5.30, 1, _utc(14, 31)),
        _fill("s1", 5.50, 1, _utc(14, 32)),
    ]
    trades = derive_trades(fills, orders)
    assert len(trades) == 1
    assert trades[0].entry_price == 5.30
    assert trades[0].exit_price == 5.50
    assert trades[0].side == "LONG"


def test_multiple_instruments_separate_trades() -> None:
    """Different instruments produce separate trades."""
    orders = [
        _order("b1", "SPY|C|480", "BUY", 1, _utc(14, 31)),
        _order("b2", "SPY|C|485", "BUY", 1, _utc(14, 31)),
        _order("s1", "SPY|C|480", "SELL", 1, _utc(14, 32)),
        _order("s2", "SPY|C|485", "SELL", 1, _utc(14, 32)),
    ]
    fills = [
        _fill("b1", 5.30, 1, _utc(14, 31)),
        _fill("b2", 3.10, 1, _utc(14, 31)),
        _fill("s1", 5.50, 1, _utc(14, 32)),
        _fill("s2", 3.00, 1, _utc(14, 32)),
    ]
    trades = derive_trades(fills, orders)
    assert len(trades) == 2
    instruments = {t.instrument_id for t in trades}
    assert instruments == {"SPY|C|480", "SPY|C|485"}


def test_no_fills_empty_list() -> None:
    """No fills → no trades."""
    assert derive_trades([], []) == []


def test_open_position_no_trade() -> None:
    """Buy without sell → no trade (position still open)."""
    orders = [_order("b1", "SPY|C|480", "BUY", 1)]
    fills = [_fill("b1", 5.30, 1)]
    trades = derive_trades(fills, orders)
    assert trades == []


def test_realized_pnl_long() -> None:
    """Long P&L = (exit - entry) * qty * multiplier."""
    orders = [
        _order("b1", "SPY|C|480", "BUY", 2, _utc(14, 31)),
        _order("s1", "SPY|C|480", "SELL", 2, _utc(14, 32)),
    ]
    fills = [
        _fill("b1", 5.00, 2, _utc(14, 31)),
        _fill("s1", 5.50, 2, _utc(14, 32)),
    ]
    trades = derive_trades(fills, orders)
    assert len(trades) == 1
    assert trades[0].realized_pnl == pytest.approx((5.50 - 5.00) * 2 * 100.0)


def test_fees_summed_from_entry_exit() -> None:
    """Trade fees = entry fill fees + exit fill fees."""
    orders = [
        _order("b1", "SPY|C|480", "BUY", 1, _utc(14, 31)),
        _order("s1", "SPY|C|480", "SELL", 1, _utc(14, 32)),
    ]
    fills = [
        _fill("b1", 5.00, 1, _utc(14, 31), fees=1.15),
        _fill("s1", 5.50, 1, _utc(14, 32), fees=1.15),
    ]
    trades = derive_trades(fills, orders)
    assert len(trades) == 1
    assert trades[0].fees == pytest.approx(2.30)


def test_short_trade() -> None:
    """Sell-to-open then buy-to-close → SHORT trade with correct P&L."""
    orders = [
        _order("s1", "SPY|C|480", "SELL", 1, _utc(14, 31)),
        _order("b1", "SPY|C|480", "BUY", 1, _utc(14, 32)),
    ]
    fills = [
        _fill("s1", 5.50, 1, _utc(14, 31)),
        _fill("b1", 5.30, 1, _utc(14, 32)),
    ]
    trades = derive_trades(fills, orders)
    assert len(trades) == 1
    assert trades[0].side == "SHORT"
    assert trades[0].realized_pnl == pytest.approx((5.50 - 5.30) * 1 * 100.0)


# ---------------------------------------------------------------------------
# Open position → trade with mark price (Phase 100 fix)
# ---------------------------------------------------------------------------


def test_open_position_emits_trade_with_mark() -> None:
    """Buy without sell + open_marks → 1 trade with exit_price=mark."""
    orders = [_order("b1", "SPY|C|480", "BUY", 1, _utc(14, 31))]
    fills = [_fill("b1", 5.30, 1, _utc(14, 31))]
    mark_ts = _utc(14, 35)
    trades = derive_trades(fills, orders, open_marks={"SPY|C|480": (5.80, mark_ts)})
    assert len(trades) == 1
    t = trades[0]
    assert t.instrument_id == "SPY|C|480"
    assert t.side == "LONG"
    assert t.entry_price == 5.30
    assert t.exit_price == 5.80
    assert t.exit_ts == mark_ts
    assert t.realized_pnl == pytest.approx((5.80 - 5.30) * 1 * 100.0)


def test_open_marks_none_no_open_trades() -> None:
    """Without open_marks, open positions produce no trades (backward compat)."""
    orders = [_order("b1", "SPY|C|480", "BUY", 1)]
    fills = [_fill("b1", 5.30, 1)]
    trades = derive_trades(fills, orders, open_marks=None)
    assert trades == []


def test_open_marks_multiple_lots() -> None:
    """Multiple open lots for same instrument → multiple trades."""
    orders = [
        _order("b1", "SPY|C|480", "BUY", 2, _utc(14, 31)),
        _order("b2", "SPY|C|480", "BUY", 3, _utc(14, 32)),
    ]
    fills = [
        _fill("b1", 5.00, 2, _utc(14, 31), fees=1.0),
        _fill("b2", 5.20, 3, _utc(14, 32), fees=1.5),
    ]
    mark_ts = _utc(14, 35)
    trades = derive_trades(fills, orders, open_marks={"SPY|C|480": (5.50, mark_ts)})
    assert len(trades) == 2
    assert trades[0].qty == 2
    assert trades[0].entry_price == 5.00
    assert trades[1].qty == 3
    assert trades[1].entry_price == 5.20
    # Both exit at mark
    assert trades[0].exit_price == 5.50
    assert trades[1].exit_price == 5.50


def test_open_marks_equity_multiplier() -> None:
    """Open position with multiplier=1.0 (equity) produces correct P&L."""
    orders = [_order("b1", "SPY", "BUY", 100, _utc(14, 31))]
    fills = [_fill("b1", 510.0, 100, _utc(14, 31))]
    mark_ts = _utc(14, 35)
    trades = derive_trades(fills, orders, multiplier=1.0, open_marks={"SPY": (520.0, mark_ts)})
    assert len(trades) == 1
    assert trades[0].realized_pnl == pytest.approx((520.0 - 510.0) * 100 * 1.0)
