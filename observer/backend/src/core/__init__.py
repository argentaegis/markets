"""Core canonical types — the contract between all modules.

No module may use vendor-specific or raw types across boundaries. All inter-module
communication uses these types. Providers normalize into them; strategies read them;
the API serializes them.
"""

from .candidate import Direction, EntryType, TradeCandidate
from .instrument import ContractSpec, FutureSymbol, InstrumentType, TradingSession
from .market_data import Bar, DataQuality, Quote
from .portfolio import Position, PortfolioState, create_mock_portfolio
from .tick import normalize_price, ticks_between

__all__ = [
    "Bar",
    "ContractSpec",
    "create_mock_portfolio",
    "DataQuality",
    "Direction",
    "EntryType",
    "FutureSymbol",
    "InstrumentType",
    "Position",
    "PortfolioState",
    "Quote",
    "TradeCandidate",
    "TradingSession",
    "normalize_price",
    "ticks_between",
]
