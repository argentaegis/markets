"""Tests for DummyStrategy implementation."""

from __future__ import annotations

from datetime import timedelta

from core.candidate import Direction, EntryType
from state.context import Context
from strategies.base import BaseStrategy, Requirements
from strategies.dummy_strategy import DummyStrategy

from .conftest import T0


class TestDummyStrategyInterface:
    def test_is_base_strategy(self):
        ds = DummyStrategy()
        assert isinstance(ds, BaseStrategy)

    def test_name_class_constant(self):
        assert DummyStrategy.NAME == "dummy"

    def test_name_is_dummy(self):
        ds = DummyStrategy()
        assert ds.name == "dummy"

    def test_name_property_matches_class_constant(self):
        ds = DummyStrategy()
        assert ds.name == DummyStrategy.NAME

    def test_default_symbols(self):
        ds = DummyStrategy()
        assert ds._symbols == ["ESH26"]

    def test_custom_symbols(self):
        ds = DummyStrategy(symbols=["NQH26"])
        assert ds._symbols == ["NQH26"]
        assert ds.requirements().symbols == ["NQH26"]

    def test_requirements_symbols(self):
        ds = DummyStrategy()
        req = ds.requirements()
        assert isinstance(req, Requirements)
        assert req.symbols == ["ESH26"]

    def test_requirements_timeframes(self):
        ds = DummyStrategy()
        assert ds.requirements().timeframes == ["5m"]

    def test_requirements_lookback(self):
        ds = DummyStrategy()
        assert ds.requirements().lookback == 1

    def test_requirements_no_quotes(self):
        ds = DummyStrategy()
        assert ds.requirements().needs_quotes is False


class TestDummyStrategyEvaluate:
    def test_returns_one_candidate(self, ctx_with_bars: Context):
        ds = DummyStrategy()
        candidates = ds.evaluate(ctx_with_bars)
        assert len(candidates) == 1

    def test_candidate_symbol(self, ctx_with_bars: Context):
        c = DummyStrategy().evaluate(ctx_with_bars)[0]
        assert c.symbol == "ESH26"

    def test_candidate_strategy(self, ctx_with_bars: Context):
        c = DummyStrategy().evaluate(ctx_with_bars)[0]
        assert c.strategy == "dummy"

    def test_candidate_direction(self, ctx_with_bars: Context):
        c = DummyStrategy().evaluate(ctx_with_bars)[0]
        assert c.direction == Direction.LONG

    def test_candidate_entry_type(self, ctx_with_bars: Context):
        c = DummyStrategy().evaluate(ctx_with_bars)[0]
        assert c.entry_type == EntryType.LIMIT

    def test_candidate_entry_price_is_last_close(self, ctx_with_bars: Context):
        c = DummyStrategy().evaluate(ctx_with_bars)[0]
        assert c.entry_price == 5403.75

    def test_candidate_stop_price(self, ctx_with_bars: Context):
        c = DummyStrategy().evaluate(ctx_with_bars)[0]
        assert c.stop_price == 5403.75 - 2.0

    def test_candidate_targets(self, ctx_with_bars: Context):
        c = DummyStrategy().evaluate(ctx_with_bars)[0]
        assert c.targets == [5403.75 + 2.0, 5403.75 + 4.0]

    def test_candidate_score(self, ctx_with_bars: Context):
        c = DummyStrategy().evaluate(ctx_with_bars)[0]
        assert c.score == 50.0

    def test_candidate_explain(self, ctx_with_bars: Context):
        c = DummyStrategy().evaluate(ctx_with_bars)[0]
        assert len(c.explain) == 3
        assert "Dummy strategy" in c.explain[0]

    def test_candidate_valid_until(self, ctx_with_bars: Context):
        c = DummyStrategy().evaluate(ctx_with_bars)[0]
        assert c.valid_until == T0 + timedelta(minutes=5)

    def test_candidate_tags(self, ctx_with_bars: Context):
        c = DummyStrategy().evaluate(ctx_with_bars)[0]
        assert c.tags == {"strategy": "dummy", "setup": "test"}

    def test_candidate_created_at(self, ctx_with_bars: Context):
        c = DummyStrategy().evaluate(ctx_with_bars)[0]
        assert c.created_at == T0

    def test_candidate_id_is_nonempty_string(self, ctx_with_bars: Context):
        c = DummyStrategy().evaluate(ctx_with_bars)[0]
        assert isinstance(c.id, str)
        assert len(c.id) > 0

    def test_candidate_ids_are_unique(self, ctx_with_bars: Context):
        ds = DummyStrategy()
        c1 = ds.evaluate(ctx_with_bars)[0]
        c2 = ds.evaluate(ctx_with_bars)[0]
        assert c1.id != c2.id


# ---------------------------------------------------------------------------
# Phase 3: Edge cases — no data = no candidates
# ---------------------------------------------------------------------------


class TestDummyStrategyEdgeCases:
    def test_empty_bars_returns_empty(self, ctx_empty: Context):
        ds = DummyStrategy()
        assert ds.evaluate(ctx_empty) == []

    def test_missing_required_symbol(self):
        ctx = Context(
            timestamp=T0,
            quotes={},
            bars={"NQH26": {"5m": []}},
        )
        ds = DummyStrategy()
        assert ds.evaluate(ctx) == []

    def test_symbol_present_but_wrong_timeframe(self):
        from core.market_data import Bar, DataQuality

        bar_1m = Bar(
            symbol="ESH26",
            timeframe="1m",
            open=5400.00,
            high=5401.00,
            low=5399.00,
            close=5400.50,
            volume=10_000,
            timestamp=T0,
            source="sim",
            quality=DataQuality.OK,
        )
        ctx = Context(
            timestamp=T0,
            quotes={},
            bars={"ESH26": {"1m": [bar_1m]}},
        )
        ds = DummyStrategy()
        assert ds.evaluate(ctx) == []

    def test_symbol_present_timeframe_present_but_empty_list(self):
        ctx = Context(
            timestamp=T0,
            quotes={},
            bars={"ESH26": {"5m": []}},
        )
        ds = DummyStrategy()
        assert ds.evaluate(ctx) == []
