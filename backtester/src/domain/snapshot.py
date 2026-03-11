"""MarketSnapshot — ts, underlying_bar, option_quotes. Built from DataProvider output (no DataFrames).

Single typed snapshot at bar-close time. Strategy receives snapshot, never raw DataFrames.
underlying_bar=None when no bar at ts; option_quotes=None when not requested.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .bars import BarRow
from .quotes import Quotes


@dataclass
class MarketSnapshot:
    """Snapshot at a timestamp: underlying bar (or None), option quotes, metadata.

    Reasoning: Bar-close ticks drive iteration; each tick gets one snapshot.
    metadata slot for future extensions (e.g. volatility surface).
    futures_bars: bar history for futures runs; engine populates when instrument_type=future (110).
    """

    ts: datetime
    underlying_bar: BarRow | None
    option_quotes: Quotes | None
    metadata: dict[str, Any] | None = None
    futures_bars: list[BarRow] | None = None


def build_market_snapshot(
    ts: datetime,
    underlying_bar: BarRow | None,
    option_quotes: Quotes | None,
    metadata: dict[str, Any] | None = None,
    futures_bars: list[BarRow] | None = None,
) -> MarketSnapshot:
    """Build MarketSnapshot from DataProvider output. No DataFrames.

    Reasoning: Centralized constructor; DataProvider never returns DataFrames.
    futures_bars for ORB/strategizer bar history (110).
    """
    return MarketSnapshot(
        ts=ts,
        underlying_bar=underlying_bar,
        option_quotes=option_quotes,
        metadata=metadata or {},
        futures_bars=futures_bars,
    )
