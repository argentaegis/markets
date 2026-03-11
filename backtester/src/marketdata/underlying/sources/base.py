"""Provider and converter abstractions for underlying market data.

Registry picks provider + converter by name (massive, etc.). Raw→canonical conversion
centralizes format handling. Canonical ts=bar close, UTC; matches loader expectation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd


class MarketDataProvider(ABC):
    """Abstract provider for OHLCV/OHLC data.

    Reasoning: Swappable providers; get_ohlcv_raw returns raw format; converter
    normalizes for cache and export.
    """

    @abstractmethod
    def get_ohlcv_raw(self, symbol: str, start: date, end: date, interval: str) -> Any:
        """Returns provider-specific raw data (DataFrame, dict, etc.)."""
        ...


class FormatConverter(ABC):
    """Transform raw provider output to canonical DataFrame."""

    @abstractmethod
    def to_canonical(self, raw: Any) -> "pd.DataFrame":
        """Returns canonical DataFrame: ts (datetime UTC), open, high, low, close, volume.
        Compatible with DataProvider underlying bar format."""
        ...
