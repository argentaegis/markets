"""Futures domain — FuturesContractSpec, TradingSession.

Separate from options ContractSpec. Enables backtester to run futures
strategies with tick_size, point_value, and session.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class TradingSession:
    """Named trading session with time boundaries.

    Minimal copy for backtester; no observer dependency (S1).
    """

    name: str
    start_time: time
    end_time: time
    timezone: str


@dataclass(frozen=True)
class FuturesContractSpec:
    """Immutable contract spec for a futures instrument.

    tick_size and point_value critical for fill alignment (090) and P&L.
    multiplier for futures = point_value (ES=50, NQ=20).
    timezone, start_time, end_time satisfy strategizer ContractSpecView (100).
    """

    symbol: str  # e.g. "ESH26", "NQH26"
    tick_size: float  # e.g. 0.25 for ES
    point_value: float  # e.g. 50 for ES, 20 for NQ
    session: TradingSession

    @property
    def timezone(self) -> str:
        return self.session.timezone

    @property
    def start_time(self) -> time:
        return self.session.start_time

    @property
    def end_time(self) -> time:
        return self.session.end_time
