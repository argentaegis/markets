"""Tests for core recommendation types — Direction, EntryType, TradeCandidate.

Covers enum values, all required fields, immutability, and unconstrained
score/explain at the type level.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.candidate import Direction, EntryType, TradeCandidate

NOW_UTC = datetime(2026, 2, 24, 14, 35, 0, tzinfo=timezone.utc)


class TestDirection:
    def test_long(self):
        assert Direction.LONG.value == "LONG"

    def test_short(self):
        assert Direction.SHORT.value == "SHORT"


class TestEntryType:
    def test_market(self):
        assert EntryType.MARKET.value == "MARKET"

    def test_limit(self):
        assert EntryType.LIMIT.value == "LIMIT"

    def test_stop(self):
        assert EntryType.STOP.value == "STOP"


def _make_candidate(**overrides) -> TradeCandidate:
    defaults = dict(
        id="tc-001",
        symbol="ESH26",
        strategy="orb_5m",
        direction=Direction.LONG,
        entry_type=EntryType.STOP,
        entry_price=5405.50,
        stop_price=5398.50,
        targets=[5412.50, 5419.50],
        score=72.5,
        explain=["ORB breakout above range", "Risk: 28 ticks"],
        valid_until=NOW_UTC + timedelta(hours=5),
        tags={"setup": "orb", "session": "rth"},
        created_at=NOW_UTC,
    )
    defaults.update(overrides)
    return TradeCandidate(**defaults)


class TestTradeCandidate:
    def test_creation_all_fields(self):
        tc = _make_candidate()
        assert tc.id == "tc-001"
        assert tc.symbol == "ESH26"
        assert tc.strategy == "orb_5m"
        assert tc.direction == Direction.LONG
        assert tc.entry_type == EntryType.STOP
        assert tc.entry_price == 5405.50
        assert tc.stop_price == 5398.50
        assert tc.targets == [5412.50, 5419.50]
        assert tc.score == 72.5
        assert tc.explain == ["ORB breakout above range", "Risk: 28 ticks"]
        assert tc.valid_until > NOW_UTC
        assert tc.tags == {"setup": "orb", "session": "rth"}
        assert tc.created_at == NOW_UTC

    def test_immutability(self):
        tc = _make_candidate()
        with pytest.raises(AttributeError):
            tc.score = 99.0

    def test_short_direction(self):
        tc = _make_candidate(direction=Direction.SHORT)
        assert tc.direction == Direction.SHORT

    def test_score_accepts_any_float(self):
        tc_negative = _make_candidate(score=-10.0)
        assert tc_negative.score == -10.0

        tc_large = _make_candidate(score=999.9)
        assert tc_large.score == 999.9

        tc_zero = _make_candidate(score=0.0)
        assert tc_zero.score == 0.0

    def test_explain_accepts_empty_list(self):
        tc = _make_candidate(explain=[])
        assert tc.explain == []

    def test_explain_accepts_single_item(self):
        tc = _make_candidate(explain=["one reason"])
        assert len(tc.explain) == 1

    def test_explain_accepts_many_items(self):
        tc = _make_candidate(explain=[f"reason {i}" for i in range(10)])
        assert len(tc.explain) == 10

    def test_empty_tags(self):
        tc = _make_candidate(tags={})
        assert tc.tags == {}

    def test_limit_entry_type(self):
        tc = _make_candidate(entry_type=EntryType.LIMIT)
        assert tc.entry_type == EntryType.LIMIT

    def test_market_entry_type(self):
        tc = _make_candidate(entry_type=EntryType.MARKET)
        assert tc.entry_type == EntryType.MARKET
