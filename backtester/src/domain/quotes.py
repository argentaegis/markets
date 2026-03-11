"""Quotes, Quote, QuoteStatus — per-contract quotes at a timestamp.

Never silently omit requested contracts; Quotes.quotes has entry for every contract_id
(Quote | QuoteStatus | None). Crossed markets sanitized and flagged — avoid invalid
bid>ask breaking FillModel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class QuoteStatus(str, Enum):
    """Explicit status for missing/stale quotes; clearer than None alone."""

    MISSING = "MISSING"
    STALE = "STALE"


def _sanitize_crossed(bid: float, ask: float, mid: float | None) -> tuple[float, float, bool]:
    """Preserve mid; set bid/ask around it. Returns (bid, ask, crossed)."""
    if bid <= ask:
        return (bid, ask, False)
    m = mid if mid is not None else (bid + ask) / 2
    return (min(bid, m), max(ask, m), True)


@dataclass
class Quote:
    """Per-contract quote. bid <= ask after sanitization; crossed_market flag if sanitized.

    Reasoning: from_raw sanitizes crossed markets so FillModel always gets valid bid/ask.
    crossed_market flag enables diagnostics (reporter tracks sanitized count).
    """

    bid: float
    ask: float
    mid: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None
    last: float | None = None
    open_interest: float | None = None
    iv: float | None = None
    greeks: dict[str, float] | None = None
    crossed_market: bool = False

    @classmethod
    def from_raw(
        cls,
        bid: float,
        ask: float,
        mid: float | None = None,
        bid_size: float | None = None,
        ask_size: float | None = None,
        last: float | None = None,
        open_interest: float | None = None,
        iv: float | None = None,
        greeks: dict[str, float] | None = None,
    ) -> Quote:
        """Create Quote; sanitize crossed market (Option B) and set crossed_market flag."""
        b, a, crossed = _sanitize_crossed(bid, ask, mid)
        m = mid if mid is not None else ((b + a) / 2)
        return cls(
            bid=b,
            ask=a,
            mid=m,
            bid_size=bid_size,
            ask_size=ask_size,
            last=last,
            open_interest=open_interest,
            iv=iv,
            greeks=greeks,
            crossed_market=crossed,
        )


@dataclass
class QuoteError:
    """Machine-readable reason for missing/stale quote.

    Reasoning: Enables structured logging and diagnostics without string parsing.
    """

    contract_id: str
    reason: str  # e.g. "MISSING", "STALE"
    detail: str | None = None


@dataclass
class Quotes:
    """Per-contract quotes at a timestamp. Mapping has entry for every requested contract_id.

    Reasoning: No silent omission; callers can detect missing via None/QuoteStatus.
    errors list provides machine-readable reasons for missingness.
    """

    ts: datetime
    quotes: dict[str, Quote | QuoteStatus | None]
    errors: list[QuoteError] = field(default_factory=list)

    def __post_init__(self) -> None:
        assert isinstance(self.quotes, dict)

    def get(self, contract_id: str) -> Quote | QuoteStatus | None:
        return self.quotes.get(contract_id)
