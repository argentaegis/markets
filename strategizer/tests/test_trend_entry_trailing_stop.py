"""Unit tests for trend_entry_trailing_stop strategy (Plan 150)."""

from datetime import datetime, timezone

from strategizer.strategies.trend_entry_trailing_stop import TrendEntryTrailingStopStrategy
from strategizer.types import BarInput, Signal


def _bar(ts_str: str, close: float) -> BarInput:
    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    return BarInput(ts=ts, open=close - 1, high=close + 1, low=close - 1, close=close, volume=100)


class _MockSpec:
    tick_size = 0.25
    point_value = 50.0
    timezone = "America/New_York"
    start_time = "09:30:00"
    end_time = "16:00:00"


class _EmptyPortfolio:
    def get_positions(self):
        return {}

    def get_cash(self):
        return 0.0

    def get_equity(self):
        return 0.0


def test_first_cross_long_emits_signal() -> None:
    """Bar low cross above MA emits LONG signal with trailing_stop_ticks."""
    strat = TrendEntryTrailingStopStrategy(
        symbols=["ESH26"],
        ma_period=5,
        trailing_stop_ticks=4,
    )
    # prev_low=97 < MA(98.4), curr_low=99 >= MA -> bar low cross above (need 6 bars for ma_period+1)
    bars = [
        _bar("2026-01-02T14:05Z", 97),
        _bar("2026-01-02T14:10Z", 98),
        _bar("2026-01-02T14:15Z", 98),
        _bar("2026-01-02T14:20Z", 98),
        _bar("2026-01-02T14:25Z", 98),
        _bar("2026-01-02T14:30Z", 100),  # low=99 crosses above MA
    ]
    ts = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)
    signals = strat.evaluate(
        ts=ts,
        bars_by_symbol={"ESH26": {"1m": bars}},
        specs={"ESH26": _MockSpec()},
        portfolio=_EmptyPortfolio(),
        strategy_params={"direction": "LONG"},
    )
    assert len(signals) == 1
    assert signals[0].direction == "LONG"
    assert signals[0].trailing_stop_ticks == 4
    assert signals[0].entry_type == "MARKET"


def test_first_cross_short_emits_signal() -> None:
    """Bar high cross below MA emits SHORT signal."""
    strat = TrendEntryTrailingStopStrategy(
        symbols=["ESH26"],
        ma_period=5,
        trailing_stop_ticks=4,
    )
    # prev_high=103 > MA(101.6), curr_high=101 <= MA -> bar high cross below
    bars = [
        _bar("2026-01-02T14:05Z", 103),
        _bar("2026-01-02T14:10Z", 102),
        _bar("2026-01-02T14:15Z", 102),
        _bar("2026-01-02T14:20Z", 102),
        _bar("2026-01-02T14:25Z", 102),
        _bar("2026-01-02T14:30Z", 100),  # high=101 crosses below MA
    ]
    ts = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)
    signals = strat.evaluate(
        ts=ts,
        bars_by_symbol={"ESH26": {"1m": bars}},
        specs={"ESH26": _MockSpec()},
        portfolio=_EmptyPortfolio(),
        strategy_params={"direction": "SHORT"},
    )
    assert len(signals) == 1
    assert signals[0].direction == "SHORT"
    assert signals[0].trailing_stop_ticks == 4


def test_no_cross_returns_empty() -> None:
    """No cross returns empty."""
    strat = TrendEntryTrailingStopStrategy(symbols=["ESH26"], ma_period=5)
    bars = [
        _bar("2026-01-02T14:10Z", 100),
        _bar("2026-01-02T14:15Z", 101),
        _bar("2026-01-02T14:20Z", 102),
        _bar("2026-01-02T14:25Z", 103),
        _bar("2026-01-02T14:30Z", 104),  # All above MA, no cross
    ]
    ts = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)
    signals = strat.evaluate(
        ts=ts,
        bars_by_symbol={"ESH26": {"1m": bars}},
        specs={"ESH26": _MockSpec()},
        portfolio=_EmptyPortfolio(),
        strategy_params={"direction": "LONG"},
    )
    assert len(signals) == 0
