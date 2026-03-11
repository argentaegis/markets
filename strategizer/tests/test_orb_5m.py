"""Tests for ORB 5m strategy."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from strategizer.strategies.orb_5m import ORB5mStrategy
from strategizer.types import BarInput


def _ny_ts(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    tz = ZoneInfo("America/New_York")
    return datetime(year, month, day, hour, minute, 0, tzinfo=tz)


def _make_bar(ts: datetime, open_p: float, high: float, low: float, close: float, volume: int = 1000) -> BarInput:
    return BarInput(ts=ts, open=open_p, high=high, low=low, close=close, volume=volume)


class _MockSpec:
    """Minimal ContractSpecView for tests."""

    def __init__(
        self,
        tick_size: float = 0.25,
        point_value: float = 50.0,
        timezone: str = "America/New_York",
        start_time: time = time(9, 30),
        end_time: time = time(16, 0),
    ) -> None:
        self.tick_size = tick_size
        self.point_value = point_value
        self.timezone = timezone
        self.start_time = start_time
        self.end_time = end_time


class _MockPortfolio:
    def get_positions(self) -> dict:
        return {}

    def get_cash(self) -> float:
        return 0.0

    def get_equity(self) -> float:
        return 0.0


def test_orb_implements_strategy() -> None:
    strategy = ORB5mStrategy()
    assert strategy.name == "orb_5m"
    req = strategy.requirements()
    assert req.symbols == ["ESH1"]
    assert set(req.timeframes) == {"1m"}
    assert req.lookback == 80


def test_orb_no_bars_returns_empty() -> None:
    strategy = ORB5mStrategy()
    spec = _MockSpec()
    ts = _ny_ts(2026, 1, 15, 10, 0)
    result = strategy.evaluate(
        ts=ts,
        bars_by_symbol={"ESH1": {"1m": []}},
        specs={"ESH1": spec},
        portfolio=_MockPortfolio(),
    )
    assert result == []


def test_orb_pre_market_only_no_or() -> None:
    """Pre-market bars only — no OR identified, no signal."""
    strategy = ORB5mStrategy()
    spec = _MockSpec()
    ts = _ny_ts(2026, 1, 15, 9, 25)
    bars = [
        _make_bar(ts, 5400, 5402, 5398, 5401),
    ]
    result = strategy.evaluate(
        ts=ts,
        bars_by_symbol={"ESH1": {"1m": bars}},
        specs={"ESH1": spec},
        portfolio=_MockPortfolio(),
    )
    assert result == []


def _orb_or_bars() -> list:
    """First 5 RTH bars (9:31-9:35) — OR high 5410, low 5405."""
    return [
        _make_bar(_ny_ts(2026, 1, 15, 9, 31), 5404, 5407, 5405, 5406),
        _make_bar(_ny_ts(2026, 1, 15, 9, 32), 5405, 5408, 5405, 5407),
        _make_bar(_ny_ts(2026, 1, 15, 9, 33), 5406, 5409, 5405, 5408),
        _make_bar(_ny_ts(2026, 1, 15, 9, 34), 5407, 5410, 5405, 5409),
        _make_bar(_ny_ts(2026, 1, 15, 9, 35), 5408, 5410, 5405, 5408),  # OR: high 5410, low 5405
    ]


def test_orb_identifies_or_first_rth_bar() -> None:
    """First 5 RTH bars set OR. Bar 6 closes within range — no breakout yet."""
    strategy = ORB5mStrategy()
    spec = _MockSpec()
    bars = _orb_or_bars() + [_make_bar(_ny_ts(2026, 1, 15, 9, 36), 5408, 5409, 5407, 5408)]
    result = strategy.evaluate(
        ts=_ny_ts(2026, 1, 15, 9, 36),
        bars_by_symbol={"ESH1": {"1m": bars}},
        specs={"ESH1": spec},
        portfolio=_MockPortfolio(),
    )
    # OR identified, but last bar closed at 5408 (within 5405-5410), no breakout
    assert result == []


def test_orb_long_breakout() -> None:
    """Bar closes above OR high — LONG signal."""
    strategy = ORB5mStrategy()
    spec = _MockSpec()
    bars = _orb_or_bars() + [
        _make_bar(_ny_ts(2026, 1, 15, 9, 36), 5409, 5415, 5408, 5412),  # close 5412 > 5410
    ]
    result = strategy.evaluate(
        ts=_ny_ts(2026, 1, 15, 9, 36),
        bars_by_symbol={"ESH1": {"1m": bars}},
        specs={"ESH1": spec},
        portfolio=_MockPortfolio(),
    )
    assert len(result) == 1
    sig = result[0]
    assert sig.symbol == "ESH1"
    assert sig.direction == "LONG"
    assert sig.entry_type == "STOP"
    assert sig.entry_price == 5410.25  # OR high + 1 tick
    assert sig.stop_price == 5404.75   # OR low - 1 tick
    assert len(sig.targets) == 2
    assert sig.valid_until is not None
    assert "above" in sig.explain[0]


def test_orb_short_breakout() -> None:
    """Bar closes below OR low — SHORT signal."""
    strategy = ORB5mStrategy()
    spec = _MockSpec()
    bars = _orb_or_bars() + [
        _make_bar(_ny_ts(2026, 1, 15, 9, 36), 5406, 5408, 5398, 5402),  # close 5402 < 5405
    ]
    result = strategy.evaluate(
        ts=_ny_ts(2026, 1, 15, 9, 36),
        bars_by_symbol={"ESH1": {"1m": bars}},
        specs={"ESH1": spec},
        portfolio=_MockPortfolio(),
    )
    assert len(result) == 1
    sig = result[0]
    assert sig.direction == "SHORT"
    assert sig.entry_price == 5404.75   # OR low - 1 tick
    assert sig.stop_price == 5410.25    # OR high + 1 tick
    assert "below" in sig.explain[0]


def test_orb_once_per_direction() -> None:
    """Second breakout in same direction — no duplicate."""
    strategy = ORB5mStrategy()
    spec = _MockSpec()
    bars = _orb_or_bars() + [
        _make_bar(_ny_ts(2026, 1, 15, 9, 36), 5409, 5415, 5408, 5412),  # LONG
        _make_bar(_ny_ts(2026, 1, 15, 9, 37), 5411, 5418, 5410, 5416),  # LONG again
    ]
    result1 = strategy.evaluate(
        ts=_ny_ts(2026, 1, 15, 9, 36),
        bars_by_symbol={"ESH1": {"1m": bars[:6]}},
        specs={"ESH1": spec},
        portfolio=_MockPortfolio(),
    )
    assert len(result1) == 1
    result2 = strategy.evaluate(
        ts=_ny_ts(2026, 1, 15, 9, 37),
        bars_by_symbol={"ESH1": {"1m": bars}},
        specs={"ESH1": spec},
        portfolio=_MockPortfolio(),
    )
    assert len(result2) == 0  # no duplicate LONG


def test_orb_range_filter_rejects_small_or() -> None:
    """OR range below min_range_ticks — rejected, no signals all session."""
    strategy = ORB5mStrategy(min_range_ticks=4, max_range_ticks=40)
    spec = _MockSpec()
    # OR range: 5410 - 5409.5 = 0.5 = 2 ticks (< min 4)
    bars = [
        _make_bar(_ny_ts(2026, 1, 15, 9, 31), 5409.25, 5410, 5409.5, 5409.75),
        _make_bar(_ny_ts(2026, 1, 15, 9, 32), 5409.5, 5410, 5409.5, 5409.75),
        _make_bar(_ny_ts(2026, 1, 15, 9, 33), 5409.5, 5410, 5409.5, 5409.75),
        _make_bar(_ny_ts(2026, 1, 15, 9, 34), 5409.5, 5410, 5409.5, 5409.75),
        _make_bar(_ny_ts(2026, 1, 15, 9, 35), 5409.5, 5410, 5409.5, 5409.75),
        _make_bar(_ny_ts(2026, 1, 15, 9, 36), 5410, 5415, 5409, 5412),
    ]
    result = strategy.evaluate(
        ts=_ny_ts(2026, 1, 15, 9, 36),
        bars_by_symbol={"ESH1": {"1m": bars}},
        specs={"ESH1": spec},
        portfolio=_MockPortfolio(),
    )
    assert result == []


def test_orb_range_filter_rejects_large_or() -> None:
    """OR range above max_range_ticks — rejected."""
    strategy = ORB5mStrategy(min_range_ticks=4, max_range_ticks=40)
    spec = _MockSpec()
    # OR range: 5420 - 5400 = 80 ticks (> max 40)
    bars = [
        _make_bar(_ny_ts(2026, 1, 15, 9, 31), 5399, 5412, 5400, 5410),
        _make_bar(_ny_ts(2026, 1, 15, 9, 32), 5408, 5414, 5400, 5411),
        _make_bar(_ny_ts(2026, 1, 15, 9, 33), 5410, 5416, 5400, 5412),
        _make_bar(_ny_ts(2026, 1, 15, 9, 34), 5411, 5418, 5400, 5413),
        _make_bar(_ny_ts(2026, 1, 15, 9, 35), 5412, 5420, 5400, 5414),
        _make_bar(_ny_ts(2026, 1, 15, 9, 36), 5410, 5425, 5409, 5422),
    ]
    result = strategy.evaluate(
        ts=_ny_ts(2026, 1, 15, 9, 36),
        bars_by_symbol={"ESH1": {"1m": bars}},
        specs={"ESH1": spec},
        portfolio=_MockPortfolio(),
    )
    assert result == []


def test_orb_new_session_resets_state() -> None:
    """New session date resets OR and fired directions."""
    strategy = ORB5mStrategy()
    spec = _MockSpec()
    # Day 1: OR + LONG breakout
    bars_day1 = _orb_or_bars() + [
        _make_bar(_ny_ts(2026, 1, 15, 9, 36), 5409, 5415, 5408, 5412),
    ]
    result1 = strategy.evaluate(
        ts=_ny_ts(2026, 1, 15, 9, 36),
        bars_by_symbol={"ESH1": {"1m": bars_day1}},
        specs={"ESH1": spec},
        portfolio=_MockPortfolio(),
    )
    assert len(result1) == 1

    # Day 2: new OR, new LONG breakout allowed
    bars_day2 = [
        _make_bar(_ny_ts(2026, 1, 16, 9, 31), 5418, 5422, 5420, 5421),
        _make_bar(_ny_ts(2026, 1, 16, 9, 32), 5419, 5423, 5420, 5422),
        _make_bar(_ny_ts(2026, 1, 16, 9, 33), 5420, 5424, 5420, 5422),
        _make_bar(_ny_ts(2026, 1, 16, 9, 34), 5421, 5425, 5420, 5422),
        _make_bar(_ny_ts(2026, 1, 16, 9, 35), 5422, 5425, 5420, 5422),
        _make_bar(_ny_ts(2026, 1, 16, 9, 36), 5422, 5430, 5421, 5428),
    ]
    result2 = strategy.evaluate(
        ts=_ny_ts(2026, 1, 16, 9, 36),
        bars_by_symbol={"ESH1": {"1m": bars_day2}},
        specs={"ESH1": spec},
        portfolio=_MockPortfolio(),
    )
    assert len(result2) == 1
    assert result2[0].entry_price == 5425.25  # new OR high + tick


def test_orb_prices_tick_normalized() -> None:
    """Entry, stop, targets are tick-aligned (0.25 for ES)."""
    strategy = ORB5mStrategy()
    spec = _MockSpec(tick_size=0.25)
    bars = _orb_or_bars() + [
        _make_bar(_ny_ts(2026, 1, 15, 9, 36), 5409, 5415, 5408, 5412),
    ]
    result = strategy.evaluate(
        ts=_ny_ts(2026, 1, 15, 9, 36),
        bars_by_symbol={"ESH1": {"1m": bars}},
        specs={"ESH1": spec},
        portfolio=_MockPortfolio(),
    )
    sig = result[0]
    assert sig.entry_price == 5410.25
    assert sig.stop_price == 5404.75
    # Targets: 1R and 2R from entry
    assert sig.targets[0] == 5415.75  # entry + 1R
    assert sig.targets[1] == 5421.25  # entry + 2R
