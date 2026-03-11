"""Tests for CandidateStore — storage, dedup, expiration."""

from __future__ import annotations

from datetime import timedelta

from core.candidate import Direction, TradeCandidate
from engine.candidate_store import CandidateStore

from .conftest import T0, T1, T2, make_candidate


class TestAdd:
    def test_add_stores_candidates(self):
        store = CandidateStore()
        c = make_candidate()
        added = store.add([c])
        assert len(added) == 1
        assert added[0] is c

    def test_add_multiple(self):
        store = CandidateStore()
        c1 = make_candidate(candidate_id="id-1", symbol="ESH26")
        c2 = make_candidate(candidate_id="id-2", symbol="NQH26")
        added = store.add([c1, c2])
        assert len(added) == 2

    def test_add_empty_list(self):
        store = CandidateStore()
        added = store.add([])
        assert added == []


class TestGetActive:
    def test_returns_non_expired(self):
        store = CandidateStore()
        c = make_candidate(timestamp=T0, valid_minutes=5)
        store.add([c])
        active = store.get_active(now=T0)
        assert len(active) == 1
        assert active[0] is c

    def test_excludes_expired(self):
        store = CandidateStore()
        c = make_candidate(timestamp=T0, valid_minutes=5)
        store.add([c])
        after_expiry = T0 + timedelta(minutes=6)
        active = store.get_active(now=after_expiry)
        assert active == []

    def test_boundary_at_valid_until(self):
        store = CandidateStore()
        c = make_candidate(timestamp=T0, valid_minutes=5)
        store.add([c])
        exactly_at = T0 + timedelta(minutes=5)
        active = store.get_active(now=exactly_at)
        assert active == []

    def test_empty_store(self):
        store = CandidateStore()
        assert store.get_active(now=T0) == []


class TestInvalidateExpired:
    def test_removes_expired_and_returns_them(self):
        store = CandidateStore()
        c = make_candidate(timestamp=T0, valid_minutes=5)
        store.add([c])
        after_expiry = T0 + timedelta(minutes=6)
        expired = store.invalidate_expired(now=after_expiry)
        assert len(expired) == 1
        assert expired[0] is c
        assert store.get_active(now=after_expiry) == []

    def test_keeps_non_expired(self):
        store = CandidateStore()
        c_soon = make_candidate(candidate_id="soon", timestamp=T0, valid_minutes=2)
        c_later = make_candidate(candidate_id="later", timestamp=T0, valid_minutes=10)
        store.add([c_soon, c_later])
        mid = T0 + timedelta(minutes=3)
        expired = store.invalidate_expired(now=mid)
        assert len(expired) == 1
        assert expired[0].id == "soon"
        active = store.get_active(now=mid)
        assert len(active) == 1
        assert active[0].id == "later"

    def test_no_expired(self):
        store = CandidateStore()
        c = make_candidate(timestamp=T0, valid_minutes=10)
        store.add([c])
        expired = store.invalidate_expired(now=T0)
        assert expired == []


class TestDeduplication:
    def test_same_key_replaces(self):
        store = CandidateStore()
        c_old = make_candidate(candidate_id="old", entry_price=5400.0, timestamp=T0)
        store.add([c_old])

        c_new = make_candidate(candidate_id="new", entry_price=5410.0, timestamp=T1)
        added = store.add([c_new])

        assert len(added) == 1
        assert added[0].id == "new"
        active = store.get_active(now=T1)
        assert len(active) == 1
        assert active[0].id == "new"
        assert active[0].entry_price == 5410.0

    def test_different_symbol_no_dedup(self):
        store = CandidateStore()
        c1 = make_candidate(candidate_id="es", symbol="ESH26")
        c2 = make_candidate(candidate_id="nq", symbol="NQH26")
        store.add([c1])
        store.add([c2])
        active = store.get_active(now=T0)
        assert len(active) == 2

    def test_different_direction_no_dedup(self):
        store = CandidateStore()
        c_long = make_candidate(candidate_id="long", direction=Direction.LONG)
        c_short = make_candidate(candidate_id="short", direction=Direction.SHORT)
        store.add([c_long])
        store.add([c_short])
        active = store.get_active(now=T0)
        assert len(active) == 2

    def test_different_strategy_no_dedup(self):
        store = CandidateStore()
        c1 = make_candidate(candidate_id="dummy", strategy="dummy")
        c2 = make_candidate(candidate_id="orb", strategy="orb_5m")
        store.add([c1])
        store.add([c2])
        active = store.get_active(now=T0)
        assert len(active) == 2

    def test_expired_old_not_counted_as_dedup(self):
        store = CandidateStore()
        c_old = make_candidate(candidate_id="old", timestamp=T0, valid_minutes=1)
        store.add([c_old])
        store.invalidate_expired(now=T0 + timedelta(minutes=2))

        c_new = make_candidate(candidate_id="new", timestamp=T1, valid_minutes=5)
        added = store.add([c_new])
        assert len(added) == 1
        active = store.get_active(now=T1)
        assert len(active) == 1
        assert active[0].id == "new"


class TestEnforceRetention:
    def test_removes_oldest_when_over_limit(self):
        store = CandidateStore()
        c1 = make_candidate(candidate_id="c1", strategy="s", timestamp=T0)
        c2 = make_candidate(candidate_id="c2", strategy="s", timestamp=T1, direction=Direction.SHORT)
        c3 = make_candidate(candidate_id="c3", strategy="s", timestamp=T2, symbol="NQH26")
        store.add([c1, c2, c3])

        removed = store.enforce_retention(max_per_strategy=2)
        assert len(removed) == 1
        assert removed[0].id == "c1"
        assert len(store._candidates) == 2

    def test_returns_removed_candidates(self):
        store = CandidateStore()
        c1 = make_candidate(candidate_id="c1", strategy="s", timestamp=T0)
        c2 = make_candidate(candidate_id="c2", strategy="s", timestamp=T1, direction=Direction.SHORT)
        c3 = make_candidate(candidate_id="c3", strategy="s", timestamp=T2, symbol="NQH26")
        store.add([c1, c2, c3])

        removed = store.enforce_retention(max_per_strategy=2)
        assert all(isinstance(c, TradeCandidate) for c in removed)
        assert {c.id for c in removed} == {"c1"}

    def test_independent_strategy_limits(self):
        store = CandidateStore()
        s1_c1 = make_candidate(candidate_id="s1-1", strategy="alpha", timestamp=T0)
        s1_c2 = make_candidate(candidate_id="s1-2", strategy="alpha", timestamp=T1, direction=Direction.SHORT)
        s1_c3 = make_candidate(candidate_id="s1-3", strategy="alpha", timestamp=T2, symbol="NQH26")
        s2_c1 = make_candidate(candidate_id="s2-1", strategy="beta", timestamp=T0)
        store.add([s1_c1, s1_c2, s1_c3, s2_c1])

        removed = store.enforce_retention(max_per_strategy=2)
        assert len(removed) == 1
        assert removed[0].id == "s1-1"
        remaining_ids = {c.id for c in store._candidates}
        assert remaining_ids == {"s1-2", "s1-3", "s2-1"}

    def test_zero_limit_removes_all(self):
        store = CandidateStore()
        c1 = make_candidate(candidate_id="c1", strategy="s", timestamp=T0)
        c2 = make_candidate(candidate_id="c2", strategy="s", timestamp=T1, direction=Direction.SHORT)
        store.add([c1, c2])

        removed = store.enforce_retention(max_per_strategy=0)
        assert len(removed) == 2
        assert store._candidates == []

    def test_at_limit_no_removal(self):
        store = CandidateStore()
        c1 = make_candidate(candidate_id="c1", strategy="s", timestamp=T0)
        c2 = make_candidate(candidate_id="c2", strategy="s", timestamp=T1, direction=Direction.SHORT)
        store.add([c1, c2])

        removed = store.enforce_retention(max_per_strategy=2)
        assert removed == []
        assert len(store._candidates) == 2

    def test_under_limit_no_removal(self):
        store = CandidateStore()
        c1 = make_candidate(candidate_id="c1", strategy="s", timestamp=T0)
        store.add([c1])

        removed = store.enforce_retention(max_per_strategy=5)
        assert removed == []
        assert len(store._candidates) == 1

    def test_empty_store(self):
        store = CandidateStore()
        removed = store.enforce_retention(max_per_strategy=10)
        assert removed == []
