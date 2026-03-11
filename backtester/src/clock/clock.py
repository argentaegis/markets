"""Clock — iter_times for bar-close timestamps.

Drives simulation loop. Each yielded ts = bar close time (end of interval).
Uses NYSE calendar; side='right' ensures bar closes align with trading minutes.
1d/1h/1m supported; 1h/1m use session open/close for intraday alignment.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

import exchange_calendars as xcals
import pandas as pd


def _get_calendar(calendar: object | None):
    """Get NYSE calendar with side='right' (bar closes are trading minutes)."""
    if calendar is not None:
        return calendar
    return xcals.get_calendar("XNYS", side="right")


def _to_utc_datetime(ts: pd.Timestamp) -> datetime:
    """Convert pandas Timestamp to datetime with UTC."""
    if ts.tzinfo is None:
        return ts.to_pydatetime().replace(tzinfo=timezone.utc)
    return ts.tz_convert(timezone.utc).to_pydatetime()


def _normalize_range(start: datetime, end: datetime) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return timezone-aware UTC Timestamps for start/end."""
    start_ts = pd.Timestamp(start) if start.tzinfo else pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end) if end.tzinfo else pd.Timestamp(end, tz="UTC")
    if start_ts.tzinfo is None:
        start_ts = start_ts.tz_localize("UTC")
    if end_ts.tzinfo is None:
        end_ts = end_ts.tz_localize("UTC")
    return start_ts, end_ts


def _iter_1d(cal: object, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> Iterator[datetime]:
    """Yield daily bar-close timestamps."""
    start_date = start_ts.normalize().tz_localize(None)
    end_date = (end_ts.normalize() + pd.Timedelta(days=1)).tz_localize(None)
    sessions = cal.sessions_in_range(start_date, end_date)
    for session in sessions:
        close = cal.schedule.loc[session, "close"]
        if start_ts <= close <= end_ts:
            yield _to_utc_datetime(close)


def _iter_1h(cal: object, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> Iterator[datetime]:
    """Yield hourly bar-close timestamps (7 per day: 10:30, 11:30, ..., 16:00 ET)."""
    start_date = start_ts.normalize().tz_localize(None)
    end_date = (end_ts.normalize() + pd.Timedelta(days=1)).tz_localize(None)
    sessions = cal.sessions_in_range(start_date, end_date)
    for session in sessions:
        session_open = cal.schedule.loc[session, "open"]
        session_close = cal.schedule.loc[session, "close"]
        if session_close < start_ts or session_open > end_ts:
            continue
        t = session_open + pd.Timedelta(hours=1)
        while t < session_close:
            if start_ts <= t <= end_ts:
                yield _to_utc_datetime(t)
            t += pd.Timedelta(hours=1)
        if start_ts <= session_close <= end_ts:
            yield _to_utc_datetime(session_close)


def _iter_1m(cal: object, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> Iterator[datetime]:
    """Yield minute bar-close timestamps."""
    start_date = start_ts.normalize().tz_localize(None)
    end_date = (end_ts.normalize() + pd.Timedelta(days=1)).tz_localize(None)
    sessions = cal.sessions_in_range(start_date, end_date)
    for session in sessions:
        session_open = cal.schedule.loc[session, "open"]
        session_close = cal.schedule.loc[session, "close"]
        if session_close < start_ts or session_open > end_ts:
            continue
        clip_start = max(start_ts, session_open + pd.Timedelta(minutes=1))
        clip_end = min(end_ts, session_close)
        if clip_start > clip_end:
            continue
        minutes = cal.minutes_in_range(clip_start, clip_end)
        if minutes is not None:
            for m in minutes:
                yield _to_utc_datetime(m)


def count_times(
    start: datetime,
    end: datetime,
    timeframe_base: str,
    calendar: object | None = None,
) -> int:
    """Return total number of bar-close timestamps for the given range.

    Same semantics as iter_times; used for progress feedback.
    """
    cal = _get_calendar(calendar)
    start_ts, end_ts = _normalize_range(start, end)
    start_date = start_ts.normalize().tz_localize(None)
    end_date = (end_ts.normalize() + pd.Timedelta(days=1)).tz_localize(None)
    sessions = cal.sessions_in_range(start_date, end_date)

    if timeframe_base == "1d":
        return sum(
            1
            for s in sessions
            if start_ts <= cal.schedule.loc[s, "close"] <= end_ts
        )
    if timeframe_base == "1h":
        n = 0
        for session in sessions:
            session_open = cal.schedule.loc[session, "open"]
            session_close = cal.schedule.loc[session, "close"]
            if session_close < start_ts or session_open > end_ts:
                continue
            t = session_open + pd.Timedelta(hours=1)
            while t < session_close:
                if start_ts <= t <= end_ts:
                    n += 1
                t += pd.Timedelta(hours=1)
            if start_ts <= session_close <= end_ts:
                n += 1
        return n
    if timeframe_base == "1m":
        n = 0
        for session in sessions:
            session_open = cal.schedule.loc[session, "open"]
            session_close = cal.schedule.loc[session, "close"]
            if session_close < start_ts or session_open > end_ts:
                continue
            clip_start = max(start_ts, session_open + pd.Timedelta(minutes=1))
            clip_end = min(end_ts, session_close)
            if clip_start > clip_end:
                continue
            minutes = cal.minutes_in_range(clip_start, clip_end)
            if minutes is not None:
                n += len(minutes)
        return n
    raise ValueError(f"timeframe_base must be '1d', '1h', or '1m'; got {timeframe_base!r}")


def iter_times(
    start: datetime,
    end: datetime,
    timeframe_base: str,
    calendar: object | None = None,
) -> Iterator[datetime]:
    """Yield bar-close timestamps for the simulation loop.

    - start, end: inclusive range [start, end]
    - timeframe_base: "1d" | "1h" | "1m"
    - All yielded datetimes are timezone-aware UTC
    - Each ts = bar close time (end of interval)
    - Uses NYSE calendar (exchange_calendars) with side="right" for bar-close semantics.

    Reasoning: Clock ts match DataProvider bar ts; no weekend/holiday times.
    Deterministic iteration for reproducible backtests.
    """
    cal = _get_calendar(calendar)
    start_ts, end_ts = _normalize_range(start, end)
    if timeframe_base == "1d":
        yield from _iter_1d(cal, start_ts, end_ts)
    elif timeframe_base == "1h":
        yield from _iter_1h(cal, start_ts, end_ts)
    elif timeframe_base == "1m":
        yield from _iter_1m(cal, start_ts, end_ts)
    else:
        raise ValueError(f"timeframe_base must be '1d', '1h', or '1m'; got {timeframe_base!r}")
