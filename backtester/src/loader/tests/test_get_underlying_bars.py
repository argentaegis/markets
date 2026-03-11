"""Phase 4.1: get_underlying_bars tests."""

import math
from datetime import datetime, timezone

import pytest

from src.domain.bars import Bars

from src.loader.tests.conftest import make_provider, utc


def test_inclusive_range() -> None:
    """UB1: Range inclusive start <= ts <= end."""
    provider = make_provider()
    start = utc(datetime(2026, 1, 2, 21, 0, 0))
    end = utc(datetime(2026, 1, 7, 21, 0, 0))
    bars = provider.get_underlying_bars("SPY", "1d", start, end)
    assert isinstance(bars, Bars)
    assert len(bars.rows) == 4  # 2,3,6,7
    for r in bars.rows:
        assert start <= r.ts <= end


def test_start_eq_end_one_bar() -> None:
    """UB2: start == end — exactly one bar if exists at that close ts."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 2, 21, 0, 0))
    bars = provider.get_underlying_bars("SPY", "1d", ts, ts)
    assert len(bars.rows) == 1
    assert bars.rows[0].ts == ts


def test_start_eq_end_no_bar() -> None:
    """UB3: start == end — no bar at that ts."""
    provider = make_provider(missing_data_policy="RETURN_EMPTY")
    ts = utc(datetime(2026, 1, 5, 21, 0, 0))  # No bar on 1/5
    bars = provider.get_underlying_bars("SPY", "1d", ts, ts)
    assert len(bars.rows) == 0


def test_bar_ts_is_close() -> None:
    """UB4: Bar ts = bar close time, UTC."""
    provider = make_provider()
    start = utc(datetime(2026, 1, 2, 21, 0, 0))
    end = utc(datetime(2026, 1, 2, 21, 0, 0))
    bars = provider.get_underlying_bars("SPY", "1d", start, end)
    assert bars.rows[0].ts.tzinfo is not None
    assert bars.rows[0].ts == start


def test_monotonic() -> None:
    """UB5: Returned bars ordered by ts ascending."""
    provider = make_provider()
    start = utc(datetime(2026, 1, 2, 21, 0, 0))
    end = utc(datetime(2026, 1, 8, 21, 0, 0))
    bars = provider.get_underlying_bars("SPY", "1d", start, end)
    for i in range(1, len(bars.rows)):
        assert bars.rows[i].ts > bars.rows[i - 1].ts


def test_unsupported_timeframe() -> None:
    """UB6: Unsupported timeframe — RAISE policy raises."""
    provider = make_provider()
    start = utc(datetime(2026, 1, 2, 21, 0, 0))
    end = utc(datetime(2026, 1, 2, 21, 0, 0))
    # 15m not in supported; RAISE policy raises MissingDataError
    with pytest.raises(Exception):
        provider.get_underlying_bars("SPY", "15m", start, end)


def test_caching_same_data() -> None:
    """UB7: Second call returns same data (cache hit)."""
    provider = make_provider()
    start = utc(datetime(2026, 1, 2, 21, 0, 0))
    end = utc(datetime(2026, 1, 2, 21, 0, 0))
    b1 = provider.get_underlying_bars("SPY", "1d", start, end)
    b2 = provider.get_underlying_bars("SPY", "1d", start, end)
    assert b1.rows[0].ts == b2.rows[0].ts
    assert b1.rows[0].close == b2.rows[0].close


def test_return_type_bars() -> None:
    """UB8: Return type is Bars (domain object)."""
    provider = make_provider()
    start = utc(datetime(2026, 1, 2, 21, 0, 0))
    end = utc(datetime(2026, 1, 2, 21, 0, 0))
    bars = provider.get_underlying_bars("SPY", "1d", start, end)
    assert isinstance(bars, Bars)


def test_no_nan_in_bars() -> None:
    """UB9: No NaN in returned bars."""
    provider = make_provider()
    start = utc(datetime(2026, 1, 2, 21, 0, 0))
    end = utc(datetime(2026, 1, 8, 21, 0, 0))
    bars = provider.get_underlying_bars("SPY", "1d", start, end)
    for r in bars.rows:
        assert not math.isnan(r.open)
        assert not math.isnan(r.close)
        assert not math.isnan(r.volume)
