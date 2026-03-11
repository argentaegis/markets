"""Instrument identity types — InstrumentType, FutureSymbol, ContractSpec, TradingSession.

Canonical types for identifying instruments and their trading parameters.
FutureSymbol.to_symbol() produces the canonical symbol string used as the key
across all state lookups, quotes, bars, and trade candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from enum import Enum


class InstrumentType(str, Enum):
    """Asset class discriminator.

    Reasoning: Strategies and providers need to branch on instrument type
    without string comparisons. str mixin enables clean JSON serialization.
    """

    FUTURE = "FUTURE"
    EQUITY = "EQUITY"
    OPTION = "OPTION"


@dataclass(frozen=True)
class FutureSymbol:
    """Futures contract identity: root + contract code + alias.

    Reasoning: Separating root from contract code allows roll logic and
    front-month resolution. to_symbol() produces the canonical key used
    everywhere (state store, quotes, bars).
    """

    root: str
    contract_code: str
    front_month_alias: str

    def to_symbol(self) -> str:
        """Canonical symbol string, e.g. 'ESH26'."""
        return f"{self.root}{self.contract_code}"


@dataclass(frozen=True)
class TradingSession:
    """Named trading session with time boundaries.

    Reasoning: Strategies must know session bounds (RTH open/close) for
    entry timing and validity windows. contains() enables clean session checks.

    V1 limitation: start_time must be < end_time (no midnight crossing).
    ETH sessions that wrap midnight require a crosses_midnight extension.
    """

    name: str
    start_time: time
    end_time: time
    timezone: str

    def contains(self, t: time) -> bool:
        """True if t is within [start_time, end_time)."""
        return self.start_time <= t < self.end_time


@dataclass(frozen=True)
class ContractSpec:
    """Immutable trading parameters for one contract.

    Reasoning: tick_size and point_value are critical for price normalization
    and risk/P&L calculations. session links the contract to its trading hours.
    symbol matches FutureSymbol.to_symbol() convention.
    """

    symbol: str
    instrument_type: InstrumentType
    tick_size: float
    point_value: float
    session: TradingSession
