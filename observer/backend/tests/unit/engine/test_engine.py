"""Tests for Engine — evaluation trigger, state update, full lifecycle."""

from __future__ import annotations

from datetime import timedelta

from core.market_data import Bar, DataQuality
from engine.config import EngineConfig
from engine.engine import Engine
from state.market_state import MarketState
from strategies.dummy_strategy import DummyStrategy

from .conftest import T0, T1, T2


def _make_bar(
    symbol: str = "ESH26",
    timeframe: str = "5m",
    close: float = 5403.75,
    timestamp=T0,
) -> Bar:
    return Bar(
        symbol=symbol,
        timeframe=timeframe,
        open=close - 3.0,
        high=close + 2.0,
        low=close - 4.0,
        close=close,
        volume=45_000,
        timestamp=timestamp,
        source="sim",
        quality=DataQuality.OK,
    )


def _build_engine(eval_timeframe: str = "5m") -> Engine:
    return Engine(
        strategies=[DummyStrategy()],
        state=MarketState(),
        config=EngineConfig(eval_timeframe=eval_timeframe),
    )


# ---------------------------------------------------------------------------
# Phase 3: Evaluation trigger + state update
# ---------------------------------------------------------------------------


class TestOnBarTrigger:
    def test_matching_timeframe_triggers_evaluation(self):
        eng = _build_engine(eval_timeframe="5m")
        bar = _make_bar(timeframe="5m")
        candidates = eng.on_bar(bar)
        assert len(candidates) == 1

    def test_non_matching_timeframe_no_evaluation(self):
        eng = _build_engine(eval_timeframe="5m")
        bar = _make_bar(timeframe="1m")
        candidates = eng.on_bar(bar)
        assert candidates == []

    def test_on_bar_updates_market_state(self):
        eng = _build_engine()
        bar = _make_bar(symbol="ESH26", timeframe="1m")
        eng.on_bar(bar)
        bars_in_state = eng._state.get_bars("ESH26", "1m", 10)
        assert len(bars_in_state) == 1
        assert bars_in_state[0] is bar

    def test_on_bar_updates_state_even_without_eval(self):
        eng = _build_engine(eval_timeframe="5m")
        bar = _make_bar(timeframe="1m")
        eng.on_bar(bar)
        assert len(eng._state.get_bars("ESH26", "1m", 10)) == 1


class TestEvaluate:
    def test_evaluate_with_timestamp(self):
        eng = _build_engine(eval_timeframe="15m")
        eng.on_bar(_make_bar(timeframe="5m"))
        candidates = eng.evaluate(timestamp=T0)
        assert len(candidates) == 1
        assert candidates[0].created_at == T0

    def test_evaluate_passes_timestamp_to_context(self):
        eng = _build_engine(eval_timeframe="15m")
        eng.on_bar(_make_bar(timeframe="5m"))
        candidates = eng.evaluate(timestamp=T1)
        assert candidates[0].valid_until == T1 + timedelta(minutes=5)

    def test_evaluate_no_data_returns_empty(self):
        eng = _build_engine()
        candidates = eng.evaluate(timestamp=T0)
        assert candidates == []

    def test_evaluate_runs_all_strategies(self):
        state = MarketState()
        eng = Engine(
            strategies=[DummyStrategy(), DummyStrategy()],
            state=state,
            config=EngineConfig(eval_timeframe="15m"),
        )
        eng.on_bar(_make_bar(timeframe="5m"))
        candidates = eng.evaluate(timestamp=T0)
        assert len(candidates) == 2


# ---------------------------------------------------------------------------
# Phase 4: Full lifecycle + end-to-end
# ---------------------------------------------------------------------------


class TestGetActiveCandidates:
    def test_delegates_to_store(self):
        eng = _build_engine()
        eng.on_bar(_make_bar(timeframe="5m", timestamp=T0))
        active = eng.get_active_candidates(now=T0)
        assert len(active) == 1

    def test_excludes_expired(self):
        eng = _build_engine()
        eng.on_bar(_make_bar(timeframe="5m", timestamp=T0))
        after = T0 + timedelta(minutes=10)
        active = eng.get_active_candidates(now=after)
        assert active == []

    def test_empty_engine(self):
        eng = _build_engine()
        assert eng.get_active_candidates(now=T0) == []


class TestInvalidateExpired:
    def test_removes_expired(self):
        eng = _build_engine()
        eng.on_bar(_make_bar(timeframe="5m", timestamp=T0))
        after = T0 + timedelta(minutes=10)
        expired = eng.invalidate_expired(now=after)
        assert len(expired) == 1
        assert eng.get_active_candidates(now=after) == []

    def test_no_expired(self):
        eng = _build_engine()
        eng.on_bar(_make_bar(timeframe="5m", timestamp=T0))
        expired = eng.invalidate_expired(now=T0)
        assert expired == []


class TestEndToEnd:
    def test_bar_to_candidate_to_expiry(self):
        """Full lifecycle: on_bar -> candidates appear -> time advances -> expired."""
        eng = _build_engine(eval_timeframe="5m")

        bar = _make_bar(timeframe="5m", close=5403.75, timestamp=T0)
        new_candidates = eng.on_bar(bar)
        assert len(new_candidates) == 1

        c = new_candidates[0]
        assert c.symbol == "ESH26"
        assert c.strategy == "dummy"
        assert c.entry_price == 5403.75
        assert c.valid_until == T0 + timedelta(minutes=5)

        active = eng.get_active_candidates(now=T0)
        assert len(active) == 1

        still_active = eng.get_active_candidates(now=T0 + timedelta(minutes=4))
        assert len(still_active) == 1

        after_expiry = T0 + timedelta(minutes=6)
        expired = eng.invalidate_expired(now=after_expiry)
        assert len(expired) == 1
        assert expired[0].id == c.id
        assert eng.get_active_candidates(now=after_expiry) == []

    def test_second_bar_replaces_candidate(self):
        """on_bar with new bar produces new candidate that replaces the old one."""
        eng = _build_engine(eval_timeframe="5m")

        eng.on_bar(_make_bar(timeframe="5m", close=5400.0, timestamp=T0))
        active_1 = eng.get_active_candidates(now=T0)
        assert len(active_1) == 1
        assert active_1[0].entry_price == 5400.0

        eng.on_bar(_make_bar(timeframe="5m", close=5410.0, timestamp=T1))
        active_2 = eng.get_active_candidates(now=T1)
        assert len(active_2) == 1
        assert active_2[0].entry_price == 5410.0

    def test_multiple_bar_timeframes(self):
        """1m bars update state but don't trigger; 5m bars trigger evaluation."""
        eng = _build_engine(eval_timeframe="5m")

        eng.on_bar(_make_bar(timeframe="1m", close=5400.0, timestamp=T0))
        assert eng.get_active_candidates(now=T0) == []

        eng.on_bar(_make_bar(timeframe="5m", close=5405.0, timestamp=T1))
        active = eng.get_active_candidates(now=T1)
        assert len(active) == 1
