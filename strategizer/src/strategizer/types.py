"""Shared types — BarInput, PositionView, Signal, ContractSpecView."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class BarInput:
    """Minimal OHLCV bar. Both observer and backtester adapt to this."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class PositionView:
    """Read-only view of a single position."""

    instrument_id: str
    qty: int
    avg_price: float


@dataclass(frozen=True)
class Signal:
    """Trading intent. Consumer adapts to TradeCandidate or Order."""

    symbol: str
    direction: str  # "LONG" | "SHORT"
    entry_type: str  # "MARKET" | "LIMIT" | "STOP"
    entry_price: float
    stop_price: float
    targets: list[float]
    qty: int = 1
    instrument_id: str | None = None  # contract_id for options; null = use symbol
    score: float = 0.0
    explain: list[str] = field(default_factory=list)
    valid_until: datetime | None = None
    trailing_stop_ticks: int | None = None  # broker-managed trailing stop (Plan 150)
