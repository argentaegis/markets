"""Shared fixtures for strategy unit tests."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from core.instrument import ContractSpec, InstrumentType, TradingSession
from core.market_data import Bar, DataQuality
from state.context import Context

T0 = datetime(2026, 2, 24, 14, 30, 0, tzinfo=timezone.utc)

ET = ZoneInfo("America/New_York")

ES_SESSION = TradingSession(
    name="RTH",
    start_time=time(9, 30),
    end_time=time(16, 0),
    timezone="America/New_York",
)

ES_SPEC = ContractSpec(
    symbol="ESH26",
    instrument_type=InstrumentType.FUTURE,
    tick_size=0.25,
    point_value=50.0,
    session=ES_SESSION,
)


def make_bar(
    symbol: str = "ESH26",
    timeframe: str = "5m",
    timestamp: datetime | None = None,
    o: float = 5400.00,
    h: float = 5405.25,
    l: float = 5398.50,
    c: float = 5403.75,
    volume: int = 10_000,
    source: str = "sim",
) -> Bar:
    """Factory for building test bars with sensible defaults."""
    return Bar(
        symbol=symbol,
        timeframe=timeframe,
        open=o,
        high=h,
        low=l,
        close=c,
        volume=volume,
        timestamp=timestamp or T0,
        source=source,
        quality=DataQuality.OK,
    )


def rth_timestamp(d: date, hour: int, minute: int) -> datetime:
    """Build a UTC datetime from an Eastern time during RTH.

    Handles DST automatically via zoneinfo.
    """
    eastern = datetime(d.year, d.month, d.day, hour, minute, tzinfo=ET)
    return eastern.astimezone(timezone.utc)


SESSION_DATE = date(2026, 2, 24)


def make_rth_bar_sequence(
    session_date: date = SESSION_DATE,
    or_high: float = 5410.00,
    or_low: float = 5400.00,
) -> dict:
    """Build a standard set of named bars for ORB testing.

    Returns a dict with keys: 'premarket', 'or_bar', 'inside', 'breakout_long',
    'breakout_short', 'second_long', 'late_session'.
    """
    ts_pre = rth_timestamp(session_date, 9, 25)
    ts_or = rth_timestamp(session_date, 9, 35)
    ts_2 = rth_timestamp(session_date, 9, 40)
    ts_3 = rth_timestamp(session_date, 9, 45)
    ts_4 = rth_timestamp(session_date, 9, 50)
    ts_5 = rth_timestamp(session_date, 9, 55)
    ts_late = rth_timestamp(session_date, 15, 50)

    return {
        "premarket": make_bar(
            timestamp=ts_pre, o=5395.00, h=5398.00, l=5393.00, c=5396.00,
        ),
        "or_bar": make_bar(
            timestamp=ts_or, o=or_low + 1, h=or_high, l=or_low, c=or_high - 2,
        ),
        "inside": make_bar(
            timestamp=ts_2, o=5403.00, h=5408.00, l=5402.00, c=5405.00,
        ),
        "breakout_long": make_bar(
            timestamp=ts_3, o=5408.00, h=5415.00, l=5407.00, c=5412.00,
        ),
        "breakout_short": make_bar(
            timestamp=ts_4, o=5402.00, h=5403.00, l=5395.00, c=5398.00,
        ),
        "second_long": make_bar(
            timestamp=ts_5, o=5411.00, h=5418.00, l=5410.00, c=5416.00,
        ),
        "late_session": make_bar(
            timestamp=ts_late, o=5420.00, h=5425.00, l=5418.00, c=5422.00,
        ),
    }


@pytest.fixture()
def sample_bar() -> Bar:
    return make_bar()


@pytest.fixture()
def ctx_with_bars(sample_bar: Bar) -> Context:
    return Context(
        timestamp=T0,
        quotes={},
        bars={"ESH26": {"5m": [sample_bar]}},
    )


@pytest.fixture()
def ctx_empty() -> Context:
    return Context(timestamp=T0, quotes={}, bars={})
