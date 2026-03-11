"""Unit tests for TrailingStopManager (Plan 150)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.broker.trailing_stop import TrailingStopManager
from src.domain.bars import BarRow
from src.domain.fill import Fill
from src.domain.order import Order
from src.domain.portfolio import PortfolioState
from src.domain.position import Position
from src.domain.snapshot import MarketSnapshot, build_market_snapshot


def _utc(h: int, m: int, s: int = 0) -> datetime:
    return datetime(2026, 1, 2, h, m, s, tzinfo=timezone.utc)


def _bar(ts: datetime, high: float, low: float) -> BarRow:
    return BarRow(ts=ts, open=low, high=high, low=low, close=high, volume=100)


def _snapshot(ts: datetime, bar: BarRow | None) -> MarketSnapshot:
    return build_market_snapshot(ts, bar, None)


def test_long_trigger_bar_low_below_threshold() -> None:
    """Long: bar.low <= high_water - N*tick triggers exit."""
    manager = TrailingStopManager()
    ts = _utc(14, 31)
    fill = Fill("o1", ts, 5400.0, 1, 0.0, None)
    order = Order("o1", ts, "ESH26", "BUY", 1, "market", None, "GTC", trailing_stop_ticks=4)
    manager.register_fill(fill, order)

    portfolio = PortfolioState(
        cash=0.0,
        positions={"ESH26": Position("ESH26", 1, 5400.0, 50.0, "future")},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=270_000.0,
    )
    # Entry bar: skip evaluation (bug fix - no same-bar trigger). Next bar triggers.
    bar_next = _bar(_utc(14, 32), high=5410.0, low=5398.0)
    snapshot = _snapshot(_utc(14, 32), bar_next)
    tick_map = {"ESH26": 0.25}

    result = manager.evaluate(portfolio, snapshot, tick_map)
    assert len(result) == 1
    fill_out, order_out = result[0]
    assert order_out.side == "SELL"
    assert order_out.qty == 1
    assert fill_out.fill_price == 5409.0  # 5410 - 4*0.25
    assert "ESH26" not in manager._state


def test_short_trigger_bar_high_above_threshold() -> None:
    """Short: bar.high >= low_water + N*tick triggers exit."""
    manager = TrailingStopManager()
    ts = _utc(14, 31)
    fill = Fill("o1", ts, 5410.0, 1, 0.0, None)
    order = Order("o1", ts, "ESH26", "SELL", 1, "market", None, "GTC", trailing_stop_ticks=4)
    manager.register_fill(fill, order)

    portfolio = PortfolioState(
        cash=270_500.0,
        positions={"ESH26": Position("ESH26", -1, 5410.0, 50.0, "future")},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=270_500.0,
    )
    # Entry bar: skip evaluation. Next bar triggers.
    bar_next = _bar(_utc(14, 32), high=5402.0, low=5398.0)
    snapshot = _snapshot(_utc(14, 32), bar_next)
    tick_map = {"ESH26": 0.25}

    result = manager.evaluate(portfolio, snapshot, tick_map)
    assert len(result) == 1
    fill_out, order_out = result[0]
    assert order_out.side == "BUY"
    assert order_out.qty == 1
    assert fill_out.fill_price == 5399.0  # 5398 + 4*0.25
    assert "ESH26" not in manager._state


def test_empty_bar_skips() -> None:
    """No bar: no trigger, no water mark update."""
    manager = TrailingStopManager()
    ts = _utc(14, 31)
    fill = Fill("o1", ts, 5400.0, 1, 0.0, None)
    order = Order("o1", ts, "ESH26", "BUY", 1, "market", None, "GTC", trailing_stop_ticks=4)
    manager.register_fill(fill, order)

    portfolio = PortfolioState(
        cash=0.0,
        positions={"ESH26": Position("ESH26", 1, 5400.0, 50.0, "future")},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=270_000.0,
    )
    snapshot = _snapshot(ts, None)
    tick_map = {"ESH26": 0.25}

    result = manager.evaluate(portfolio, snapshot, tick_map)
    assert len(result) == 0
    assert "ESH26" in manager._state


def test_no_trigger_when_bar_does_not_reach_threshold() -> None:
    """Long: bar.low > high_water - N*tick -> no trigger."""
    manager = TrailingStopManager()
    ts = _utc(14, 31)
    fill = Fill("o1", ts, 5400.0, 1, 0.0, None)
    order = Order("o1", ts, "ESH26", "BUY", 1, "market", None, "GTC", trailing_stop_ticks=4)
    manager.register_fill(fill, order)

    portfolio = PortfolioState(
        cash=0.0,
        positions={"ESH26": Position("ESH26", 1, 5400.0, 50.0, "future")},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=270_000.0,
    )
    # Entry bar: skip. Next bar: high=5410, low=5410 (flat). Threshold = 5409. low 5410 > 5409 -> no trigger.
    bar_next = _bar(_utc(14, 32), high=5410.0, low=5410.0)
    snapshot = _snapshot(_utc(14, 32), bar_next)
    tick_map = {"ESH26": 0.25}

    result = manager.evaluate(portfolio, snapshot, tick_map)
    assert len(result) == 0
    assert manager._state["ESH26"].water_mark == 5410.0


def test_register_fill_ignores_order_without_trailing_stop() -> None:
    """register_fill does nothing when order.trailing_stop_ticks is None."""
    manager = TrailingStopManager()
    ts = _utc(14, 31)
    fill = Fill("o1", ts, 5400.0, 1, 0.0, None)
    order = Order("o1", ts, "ESH26", "BUY", 1, "market", None, "GTC")  # no trailing_stop_ticks

    manager.register_fill(fill, order)
    assert len(manager._state) == 0
