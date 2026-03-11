"""iter_times tests — Phase 1 & 2 Red (040_clock_calendar).

iter_times(start, end, timeframe_base) yields bar-close timestamps.
Bar ts = bar close time (end of interval), UTC. Skip non-trading times.
Supports 1d, 1h, 1m (MVP).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from src.clock import iter_times


# ---------------------------------------------------------------------------
# Phase 1: 1d timeframe — trading days only
# ---------------------------------------------------------------------------


def test_iter_times_1d_returns_trading_days_in_range() -> None:
    """1d: Yields one bar-close per trading day in [start, end], inclusive.

    Jan 2–5 2024 = Tue–Fri = 4 trading days. Bar close = 16:00 ET = 21:00 UTC (EST).
    """
    start = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 5, 23, 59, 59, tzinfo=timezone.utc)

    result = list(iter_times(start, end, "1d"))

    assert len(result) == 4
    # Each ts is bar close: 21:00 UTC (16:00 ET in January)
    assert result[0] == datetime(2024, 1, 2, 21, 0, 0, tzinfo=timezone.utc)
    assert result[1] == datetime(2024, 1, 3, 21, 0, 0, tzinfo=timezone.utc)
    assert result[2] == datetime(2024, 1, 4, 21, 0, 0, tzinfo=timezone.utc)
    assert result[3] == datetime(2024, 1, 5, 21, 0, 0, tzinfo=timezone.utc)


def test_iter_times_1d_empty_range_when_no_trading_sessions() -> None:
    """1d: Empty when range has no trading days (e.g. weekend)."""
    start = datetime(2024, 1, 6, 0, 0, 0, tzinfo=timezone.utc)  # Saturday
    end = datetime(2024, 1, 7, 23, 59, 59, tzinfo=timezone.utc)  # Sunday

    result = list(iter_times(start, end, "1d"))

    assert len(result) == 0


def test_iter_times_1d_single_day_in_range() -> None:
    """1d: When start == end on a trading day, yield one bar close."""
    start = datetime(2024, 1, 3, 12, 0, 0, tzinfo=timezone.utc)  # Wednesday midday
    end = datetime(2024, 1, 3, 23, 59, 59, tzinfo=timezone.utc)

    result = list(iter_times(start, end, "1d"))

    assert len(result) == 1
    assert result[0] == datetime(2024, 1, 3, 21, 0, 0, tzinfo=timezone.utc)


def test_iter_times_1d_determinism() -> None:
    """1d: Same inputs yield identical sequence."""
    start = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 5, 23, 59, 59, tzinfo=timezone.utc)

    first = list(iter_times(start, end, "1d"))
    second = list(iter_times(start, end, "1d"))

    assert first == second


def test_iter_times_1d_timestamps_are_utc() -> None:
    """1d: All yielded datetimes are timezone-aware UTC."""
    start = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 3, 23, 59, 59, tzinfo=timezone.utc)

    result = list(iter_times(start, end, "1d"))

    for ts in result:
        assert ts.tzinfo is not None
        assert ts.tzinfo == timezone.utc


def test_iter_times_1d_skips_holidays() -> None:
    """1d: Skips NYSE holidays (e.g. New Year's Day)."""
    # Jan 1 2024 = Monday = New Year's Day (NYSE closed)
    start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 5, 23, 59, 59, tzinfo=timezone.utc)

    result = list(iter_times(start, end, "1d"))

    # Jan 2, 3, 4, 5 = 4 trading days; Jan 1 is holiday
    assert len(result) == 4
    dates = [ts.date() for ts in result]
    assert date(2024, 1, 1) not in dates
    assert date(2024, 1, 2) in dates


# ---------------------------------------------------------------------------
# Phase 2: 1h timeframe — hourly bar closes within market hours
# ---------------------------------------------------------------------------
# US market: 9:30–16:00 ET. Hourly bars: 9:30–10:30 (close 10:30), ..., 15:30–16:00 (close 16:00).
# 7 bars per day. EST: +5h to UTC. 10:30 ET = 15:30 UTC, 16:00 ET = 21:00 UTC.


def test_iter_times_1h_yields_hourly_bar_closes_in_market_hours() -> None:
    """1h: Yields hourly bar closes within 9:30–16:00 ET. 7 bars per trading day."""
    start = datetime(2024, 1, 2, 14, 0, 0, tzinfo=timezone.utc)  # 9:00 ET
    end = datetime(2024, 1, 2, 22, 0, 0, tzinfo=timezone.utc)   # 17:00 ET (captures close)

    result = list(iter_times(start, end, "1h"))

    # 7 hourly bar closes: 10:30, 11:30, 12:30, 13:30, 14:30, 15:30, 16:00 ET → UTC
    assert len(result) == 7
    assert result[0] == datetime(2024, 1, 2, 15, 30, 0, tzinfo=timezone.utc)  # 10:30 ET
    assert result[6] == datetime(2024, 1, 2, 21, 0, 0, tzinfo=timezone.utc)   # 16:00 ET


def test_iter_times_1h_empty_when_outside_market_hours() -> None:
    """1h: Empty when range is outside market hours (e.g. evening)."""
    start = datetime(2024, 1, 2, 22, 0, 0, tzinfo=timezone.utc)  # 17:00 ET (after close)
    end = datetime(2024, 1, 2, 23, 59, 59, tzinfo=timezone.utc)

    result = list(iter_times(start, end, "1h"))

    assert len(result) == 0


def test_iter_times_1h_spans_multiple_days() -> None:
    """1h: Correctly spans multiple trading days."""
    start = datetime(2024, 1, 2, 15, 0, 0, tzinfo=timezone.utc)   # Jan 2
    end = datetime(2024, 1, 3, 21, 0, 0, tzinfo=timezone.utc)     # Jan 3 through close (16:00 ET = 21:00 UTC)

    result = list(iter_times(start, end, "1h"))

    # Jan 2: bars from 10:30–16:00 ET (7 bars). Jan 3: same (7 bars). Total 14.
    assert len(result) == 14


# ---------------------------------------------------------------------------
# Phase 2: 1m timeframe — minute bar closes within market hours
# ---------------------------------------------------------------------------
# 9:30–16:00 ET = 390 minutes. First bar close 9:31 ET, last 16:00 ET.


def test_iter_times_1m_yields_minute_bar_closes_in_market_hours() -> None:
    """1m: Yields minute bar closes within 9:30–16:00 ET."""
    # Request first 5 minutes of trading: 9:31, 9:32, 9:33, 9:34, 9:35 ET
    # 9:31 ET = 14:31 UTC (EST)
    start = datetime(2024, 1, 2, 14, 30, 0, tzinfo=timezone.utc)  # 9:30 ET
    end = datetime(2024, 1, 2, 14, 36, 0, tzinfo=timezone.utc)    # 9:36 ET

    result = list(iter_times(start, end, "1m"))

    assert len(result) == 6  # 9:31, 9:32, 9:33, 9:34, 9:35, 9:36 ET
    assert result[0] == datetime(2024, 1, 2, 14, 31, 0, tzinfo=timezone.utc)
    assert result[5] == datetime(2024, 1, 2, 14, 36, 0, tzinfo=timezone.utc)


def test_iter_times_1m_last_bar_is_market_close() -> None:
    """1m: Last bar of day is 16:00 ET (market close)."""
    start = datetime(2024, 1, 2, 20, 59, 0, tzinfo=timezone.utc)  # 15:59 ET (first bar close in range)
    end = datetime(2024, 1, 2, 21, 1, 0, tzinfo=timezone.utc)      # 16:01 ET

    result = list(iter_times(start, end, "1m"))

    # 15:59 and 16:00 ET = 20:59 and 21:00 UTC
    assert len(result) == 2
    assert result[-1] == datetime(2024, 1, 2, 21, 0, 0, tzinfo=timezone.utc)


def test_iter_times_rejects_5m() -> None:
    """5m timeframe is no longer supported; raises ValueError."""
    start = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 3, 0, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="5m"):
        list(iter_times(start, end, "5m"))


def test_iter_times_rejects_invalid_timeframe() -> None:
    """iter_times raises ValueError for unsupported timeframe."""
    start = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 3, 0, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="15m"):
        list(iter_times(start, end, "15m"))
