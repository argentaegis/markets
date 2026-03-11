"""Phase 1.1: Bars and BarRow tests."""

import math
import pytest
from datetime import datetime, timezone

from src.domain.bars import BarRow, Bars, create_bars


def test_barrow_create() -> None:
    """B1: Create BarRow with ts, o/h/l/c, volume; all required fields present."""
    br = BarRow(
        ts=datetime(2026, 1, 2, 21, 0, 0, tzinfo=timezone.utc),
        open=480.0,
        high=485.0,
        low=478.0,
        close=483.0,
        volume=1000000,
    )
    assert br.open == 480.0
    assert br.close == 483.0
    assert br.volume == 1000000


def test_bars_create() -> None:
    """B2: Create Bars with symbol, timeframe, start, end, timezone, rows."""
    rows = [
        BarRow(
            ts=datetime(2026, 1, 2, 21, 0, 0, tzinfo=timezone.utc),
            open=480.0,
            high=485.0,
            low=478.0,
            close=483.0,
            volume=1000000,
        )
    ]
    b = Bars(
        symbol="SPY",
        timeframe="1d",
        start=datetime(2026, 1, 2, 21, 0, 0, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, 21, 0, 0, tzinfo=timezone.utc),
        timezone="UTC",
        rows=rows,
    )
    assert b.symbol == "SPY"
    assert b.timeframe == "1d"
    assert len(b.rows) == 1
    assert b.timezone == "UTC"


def test_bars_monotonic_rejected() -> None:
    """B3: Bars out of order raise."""
    ts1 = datetime(2026, 1, 3, 21, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2026, 1, 2, 21, 0, 0, tzinfo=timezone.utc)
    rows = [
        BarRow(ts=ts1, open=1, high=1, low=1, close=1, volume=1),
        BarRow(ts=ts2, open=1, high=1, low=1, close=1, volume=1),
    ]
    with pytest.raises(ValueError, match="monotonic"):
        Bars(
            symbol="SPY",
            timeframe="1d",
            start=ts2,
            end=ts1,
            timezone="UTC",
            rows=rows,
        )


def test_bars_empty_valid() -> None:
    """B4: Empty Bars valid for empty range."""
    b = Bars(
        symbol="SPY",
        timeframe="1d",
        start=datetime(2026, 1, 2, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, tzinfo=timezone.utc),
        timezone="UTC",
        rows=[],
    )
    assert len(b.rows) == 0
    assert b.start < b.end or b.start == b.end


def test_bars_timezone() -> None:
    """B5: Timezone field is set."""
    b = Bars(
        symbol="SPY",
        timeframe="1d",
        start=datetime(2026, 1, 2, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, tzinfo=timezone.utc),
        timezone="UTC",
        rows=[],
    )
    assert b.timezone == "UTC"


def test_barrow_nan_rejected() -> None:
    """B6: BarRow with NaN in required field raises."""
    with pytest.raises(ValueError, match="NaN"):
        BarRow(
            ts=datetime(2026, 1, 2, tzinfo=timezone.utc),
            open=480.0,
            high=math.nan,
            low=478.0,
            close=483.0,
            volume=1000000,
        )
