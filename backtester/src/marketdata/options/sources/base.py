"""Options provider and converter abstractions.

Chain provider returns contract list; quotes provider returns historical bid/ask.
Converters normalize to canonical metadata (underlying, expiry, strike, right,
contract_id, multiplier) and quote series (ts, bid, ask).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any


class OptionsChainProvider(ABC):
    """Abstract provider for options chain (contract list)."""

    @abstractmethod
    def get_chain_raw(
        self,
        underlying: str,
        expiration_date_gte: date,
        expiration_date_lte: date,
        *,
        strike_price_gte: float | None = None,
        strike_price_lte: float | None = None,
        limit: int | None = None,
    ) -> Any:
        """Returns provider-specific raw chain data."""
        ...


class OptionsQuotesProvider(ABC):
    """Abstract provider for historical options quotes."""

    @abstractmethod
    def get_quotes_raw(self, options_ticker: str, start: date, end: date) -> Any:
        """Returns provider-specific raw quote series."""
        ...


class OptionsChainConverter(ABC):
    """Convert raw chain to canonical metadata rows."""

    @abstractmethod
    def to_canonical(self, raw: Any) -> list[dict]:
        """Returns list of dicts: underlying, expiry, strike, right, contract_id, multiplier."""
        ...


class OptionsQuotesConverter(ABC):
    """Convert raw quotes to canonical (ts, bid, ask) series."""

    @abstractmethod
    def to_canonical(self, raw: Any) -> list[tuple]:
        """Returns list of (datetime, bid, ask) sorted by ts."""
        ...
