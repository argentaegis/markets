"""Market data types — Quote, Bar, DataQuality.

Canonical representations for real-time quote snapshots and OHLCV bars.
__post_init__ validation rejects NaN prices and negative volume/sizes,
matching the backtester's fail-fast pattern (BarRow rejects NaN).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class DataQuality(str, Enum):
    """Quality flag attached to every data point.

    Reasoning: Strategies and UI need to distinguish fresh data from stale/missing.
    Providers set this; consumers branch on it for display or evaluation gating.
    """

    OK = "OK"
    STALE = "STALE"
    MISSING = "MISSING"
    PARTIAL = "PARTIAL"


@dataclass(frozen=True)
class Quote:
    """Real-time quote snapshot for one symbol.

    Reasoning: Frozen so quotes are safe to cache and share across modules.
    __post_init__ rejects NaN prices and negative sizes/volume to catch
    data corruption at creation rather than downstream.
    """

    symbol: str
    bid: float
    ask: float
    last: float
    bid_size: int
    ask_size: int
    volume: int
    timestamp: datetime
    source: str
    quality: DataQuality

    def __post_init__(self) -> None:
        for field in ("bid", "ask", "last"):
            val = getattr(self, field)
            if isinstance(val, float) and math.isnan(val):
                raise ValueError(f"Quote.{field} cannot be NaN")
        for field in ("bid_size", "ask_size", "volume"):
            val = getattr(self, field)
            if val < 0:
                raise ValueError(f"Quote.{field} cannot be negative")


@dataclass(frozen=True)
class Bar:
    """OHLCV bar. timestamp = bar close time (UTC).

    Reasoning: Frozen for safe caching. Bar close time convention matches the
    backtester (BarRow). Strategies evaluate after bar close, so timestamp
    represents when the bar completed. __post_init__ rejects NaN and negative volume.
    """

    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    timestamp: datetime
    source: str
    quality: DataQuality

    def __post_init__(self) -> None:
        for field in ("open", "high", "low", "close"):
            val = getattr(self, field)
            if isinstance(val, float) and math.isnan(val):
                raise ValueError(f"Bar.{field} cannot be NaN")
        if self.volume < 0:
            raise ValueError("Bar.volume cannot be negative")
