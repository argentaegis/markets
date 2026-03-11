"""Recommendation types — Direction, EntryType, TradeCandidate.

TradeCandidate is the output artifact of strategy evaluation. It is informational
only (no order placement fields in V1). Score and explain constraints are not
enforced at the type level — score normalization (0-100) belongs to step 130,
and explain length (3-6) is a strategy-level guideline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Direction(str, Enum):
    """Trade direction.

    Reasoning: Strategies emit directional candidates; enum prevents typos
    and enables clean matching in ranking/filtering logic.
    """

    LONG = "LONG"
    SHORT = "SHORT"


class EntryType(str, Enum):
    """How to enter a trade.

    Reasoning: ORB uses STOP entries (buy stop above range); other strategies
    may use LIMIT or MARKET. Enum keeps the API clean.
    """

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


@dataclass(frozen=True)
class TradeCandidate:
    """Immutable trade recommendation artifact.

    Reasoning: Produced by strategies, consumed by ranking/UI/journal. Frozen
    so candidates are safe to cache, deduplicate, and persist. id should be
    a UUID string for unique identification across deduplication and journaling.
    """

    id: str
    symbol: str
    strategy: str
    direction: Direction
    entry_type: EntryType
    entry_price: float
    stop_price: float
    targets: list[float]
    score: float
    explain: list[str]
    valid_until: datetime
    tags: dict[str, str]
    created_at: datetime
