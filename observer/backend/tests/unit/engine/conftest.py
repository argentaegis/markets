"""Shared fixtures for engine unit tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.candidate import Direction, EntryType, TradeCandidate

T0 = datetime(2026, 2, 24, 14, 30, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 2, 24, 14, 35, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 2, 24, 14, 40, 0, tzinfo=timezone.utc)


def make_candidate(
    *,
    symbol: str = "ESH26",
    strategy: str = "dummy",
    direction: Direction = Direction.LONG,
    entry_price: float = 5400.0,
    valid_minutes: int = 5,
    timestamp: datetime = T0,
    candidate_id: str = "test-id-1",
) -> TradeCandidate:
    return TradeCandidate(
        id=candidate_id,
        symbol=symbol,
        strategy=strategy,
        direction=direction,
        entry_type=EntryType.LIMIT,
        entry_price=entry_price,
        stop_price=entry_price - 2.0,
        targets=[entry_price + 2.0, entry_price + 4.0],
        score=50.0,
        explain=["Test candidate"],
        valid_until=timestamp + timedelta(minutes=valid_minutes),
        tags={"strategy": strategy},
        created_at=timestamp,
    )
