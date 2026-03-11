"""Bars and BarRow — time-ordered OHLCV bar series.

Bar ts = bar close time (end of interval), UTC. Invariant: timestamps monotonic
increasing — downstream logic assumes sorted order. No NaN or negative volume —
ensures valid data for P&L and marking.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
import math


@dataclass(frozen=True)
class BarRow:
    """Single OHLCV bar. All required fields must be present; no NaN.

    Reasoning: Frozen so bars cannot be mutated after creation; safe to cache/share.
    Validation in __post_init__ fails fast on NaN or negative volume.
    """

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        for name in ("open", "high", "low", "close", "volume"):
            val = getattr(self, name)
            if isinstance(val, float) and math.isnan(val):
                raise ValueError(f"BarRow.{name} cannot be NaN")
            if isinstance(val, (int, float)) and val < 0 and name == "volume":
                raise ValueError("BarRow.volume cannot be negative")


@dataclass
class Bars:
    """Time-ordered series of OHLCV bars. Timestamps must be monotonic increasing.

    Reasoning: DataProvider returns Bars not DataFrames. Monotonic ts required
    for as-of lookups and iteration. symbol/timeframe/start/end enable range checks.
    """

    symbol: str
    timeframe: str
    start: datetime
    end: datetime
    timezone: str
    rows: list[BarRow]

    def __post_init__(self) -> None:
        # Enforce monotonic increasing timestamps
        for i in range(1, len(self.rows)):
            if self.rows[i].ts <= self.rows[i - 1].ts:
                raise ValueError(
                    f"Bars timestamps must be monotonic increasing; "
                    f"row {i} ts={self.rows[i].ts} <= row {i-1} ts={self.rows[i-1].ts}"
                )


def create_bars(
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    rows: list[BarRow],
    timezone: str = "UTC",
) -> Bars:
    """Build Bars from rows. Sorts by ts to guarantee monotonic order; rejects if duplicates.

    Reasoning: Callers may pass unsorted rows; centralizing sort here ensures invariant.
    """
    sorted_rows = sorted(rows, key=lambda r: r.ts)
    return Bars(
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        timezone=timezone,
        rows=sorted_rows,
    )
