"""Tests for ORB5mStrategy — Opening Range Breakout on 5-minute bars.

Covers: OR identification, breakout detection, price calculations,
score/explain/validity, filters, session state reset, and engine integration.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from core.candidate import Direction, EntryType
from core.instrument import ContractSpec, InstrumentType, TradingSession
from core.tick import normalize_price, ticks_between
from state.context import Context
from strategies.orb_5m import ORB5mStrategy

from .conftest import (
    ES_SPEC,
    SESSION_DATE,
    make_bar,
    make_rth_bar_sequence,
    rth_timestamp,
)

ET = ZoneInfo("America/New_York")


def _ctx(bars_list, timestamp, specs=None):
    """Build a Context from a list of bars for ESH26 5m."""
    return Context(
        timestamp=timestamp,
        quotes={},
        bars={"ESH26": {"5m": bars_list}},
        specs=specs or {"ESH26": ES_SPEC},
    )


# ---------------------------------------------------------------------------
# Phase 1: Opening range identification
# ---------------------------------------------------------------------------


class TestORBRequirements:
    def test_name_class_constant(self):
        assert ORB5mStrategy.NAME == "orb_5m"

    def test_name(self):
        s = ORB5mStrategy()
        assert s.name == "orb_5m"

    def test_name_property_matches_class_constant(self):
        s = ORB5mStrategy()
        assert s.name == ORB5mStrategy.NAME

    def test_requirements_defaults(self):
        s = ORB5mStrategy()
        r = s.requirements()
        assert r.symbols == ["ESH26"]
        assert r.timeframes == ["5m"]
        assert r.lookback == 80
        assert r.needs_quotes is False

    def test_requirements_custom_symbols(self):
        s = ORB5mStrategy(symbols=["NQH26"])
        r = s.requirements()
        assert r.symbols == ["NQH26"]


class TestOpeningRangeIdentification:
    def test_or_identified_from_first_rth_bar(self):
        seq = make_rth_bar_sequence(or_high=5410.00, or_low=5400.00)
        s = ORB5mStrategy()
        ctx = _ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp)
        s.evaluate(ctx)
        assert s._or_high == 5410.00
        assert s._or_low == 5400.00

    def test_premarket_bars_ignored(self):
        seq = make_rth_bar_sequence()
        s = ORB5mStrategy()
        ctx = _ctx([seq["premarket"]], timestamp=seq["premarket"].timestamp)
        result = s.evaluate(ctx)
        assert result == []
        assert s._or_high is None

    def test_no_bars_returns_empty(self):
        s = ORB5mStrategy()
        ctx = Context(
            timestamp=rth_timestamp(SESSION_DATE, 9, 35),
            quotes={},
            bars={},
            specs={"ESH26": ES_SPEC},
        )
        assert s.evaluate(ctx) == []

    def test_missing_spec_returns_empty(self):
        seq = make_rth_bar_sequence()
        s = ORB5mStrategy()
        ctx = _ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp, specs={})
        assert s.evaluate(ctx) == []

    def test_new_session_resets_or_state(self):
        s = ORB5mStrategy()
        seq1 = make_rth_bar_sequence(
            session_date=date(2026, 2, 24), or_high=5410.00, or_low=5400.00,
        )
        ctx1 = _ctx(
            [seq1["or_bar"], seq1["breakout_long"]],
            timestamp=seq1["breakout_long"].timestamp,
        )
        result1 = s.evaluate(ctx1)
        assert len(result1) == 1

        seq2 = make_rth_bar_sequence(
            session_date=date(2026, 2, 25), or_high=5450.00, or_low=5440.00,
        )
        ctx2 = _ctx(
            [seq2["or_bar"]],
            timestamp=seq2["or_bar"].timestamp,
        )
        s.evaluate(ctx2)
        assert s._or_high == 5450.00
        assert s._or_low == 5440.00
        assert s._fired == set()


# ---------------------------------------------------------------------------
# Phase 2: Breakout detection
# ---------------------------------------------------------------------------


class TestBreakoutDetection:
    def test_long_breakout(self):
        seq = make_rth_bar_sequence(or_high=5410.00, or_low=5400.00)
        s = ORB5mStrategy()
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"]],
            timestamp=seq["breakout_long"].timestamp,
        ))
        assert len(result) == 1
        assert result[0].direction == Direction.LONG

    def test_short_breakout(self):
        seq = make_rth_bar_sequence(or_high=5410.00, or_low=5400.00)
        s = ORB5mStrategy()
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_short"]],
            timestamp=seq["breakout_short"].timestamp,
        ))
        assert len(result) == 1
        assert result[0].direction == Direction.SHORT

    def test_inside_bar_no_candidate(self):
        seq = make_rth_bar_sequence(or_high=5410.00, or_low=5400.00)
        s = ORB5mStrategy()
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["inside"]],
            timestamp=seq["inside"].timestamp,
        ))
        assert result == []

    def test_once_per_direction_long(self):
        seq = make_rth_bar_sequence(or_high=5410.00, or_low=5400.00)
        s = ORB5mStrategy()
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))

        r1 = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"]],
            timestamp=seq["breakout_long"].timestamp,
        ))
        assert len(r1) == 1

        r2 = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"], seq["second_long"]],
            timestamp=seq["second_long"].timestamp,
        ))
        assert r2 == []

    def test_both_directions_can_fire(self):
        seq = make_rth_bar_sequence(or_high=5410.00, or_low=5400.00)
        s = ORB5mStrategy()
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))

        r_long = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"]],
            timestamp=seq["breakout_long"].timestamp,
        ))
        r_short = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"], seq["breakout_short"]],
            timestamp=seq["breakout_short"].timestamp,
        ))
        assert len(r_long) == 1
        assert r_long[0].direction == Direction.LONG
        assert len(r_short) == 1
        assert r_short[0].direction == Direction.SHORT


# ---------------------------------------------------------------------------
# Phase 3: Entry / Stop / Target calculation
# ---------------------------------------------------------------------------


class TestPriceCalculation:
    def test_long_entry_stop_targets(self):
        or_high, or_low = 5410.00, 5400.00
        tick = ES_SPEC.tick_size
        seq = make_rth_bar_sequence(or_high=or_high, or_low=or_low)
        s = ORB5mStrategy()
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"]],
            timestamp=seq["breakout_long"].timestamp,
        ))
        c = result[0]

        expected_entry = normalize_price(or_high + tick, tick)
        expected_stop = normalize_price(or_low - tick, tick)
        risk = expected_entry - expected_stop
        expected_t1 = normalize_price(expected_entry + risk, tick)
        expected_t2 = normalize_price(expected_entry + 2 * risk, tick)

        assert c.entry_price == expected_entry
        assert c.stop_price == expected_stop
        assert c.entry_type == EntryType.STOP
        assert len(c.targets) == 2
        assert c.targets[0] == expected_t1
        assert c.targets[1] == expected_t2

    def test_short_entry_stop_targets(self):
        or_high, or_low = 5410.00, 5400.00
        tick = ES_SPEC.tick_size
        seq = make_rth_bar_sequence(or_high=or_high, or_low=or_low)
        s = ORB5mStrategy()
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_short"]],
            timestamp=seq["breakout_short"].timestamp,
        ))
        c = result[0]

        expected_entry = normalize_price(or_low - tick, tick)
        expected_stop = normalize_price(or_high + tick, tick)
        risk = expected_stop - expected_entry
        expected_t1 = normalize_price(expected_entry - risk, tick)
        expected_t2 = normalize_price(expected_entry - 2 * risk, tick)

        assert c.entry_price == expected_entry
        assert c.stop_price == expected_stop
        assert c.entry_type == EntryType.STOP
        assert c.targets[0] == expected_t1
        assert c.targets[1] == expected_t2

    def test_prices_are_tick_normalized(self):
        seq = make_rth_bar_sequence(or_high=5410.13, or_low=5399.87)
        s = ORB5mStrategy()
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"]],
            timestamp=seq["breakout_long"].timestamp,
        ))
        if result:
            c = result[0]
            tick = ES_SPEC.tick_size
            assert c.entry_price == normalize_price(c.entry_price, tick)
            assert c.stop_price == normalize_price(c.stop_price, tick)
            for t in c.targets:
                assert t == normalize_price(t, tick)


# ---------------------------------------------------------------------------
# Phase 4: Score, explain, validity, tags
# ---------------------------------------------------------------------------


class TestScoreExplainValidity:
    def test_score_midpoint_range(self):
        """Range near midpoint of min/max should score ~80."""
        mid_ticks = (4 + 40) // 2
        or_range = mid_ticks * ES_SPEC.tick_size
        or_low = 5400.00
        or_high = or_low + or_range
        seq = make_rth_bar_sequence(or_high=or_high, or_low=or_low)
        s = ORB5mStrategy()
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"]],
            timestamp=seq["breakout_long"].timestamp,
        ))
        assert len(result) == 1
        assert result[0].score >= 70.0

    def test_score_extreme_range(self):
        """Range at filter boundary should score lower."""
        or_range = 5 * ES_SPEC.tick_size
        or_low = 5400.00
        or_high = or_low + or_range
        seq = make_rth_bar_sequence(or_high=or_high, or_low=or_low)
        s = ORB5mStrategy()
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"]],
            timestamp=seq["breakout_long"].timestamp,
        ))
        assert len(result) == 1
        assert result[0].score < 70.0

    def test_explain_bullets(self):
        seq = make_rth_bar_sequence(or_high=5410.00, or_low=5400.00)
        s = ORB5mStrategy()
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"]],
            timestamp=seq["breakout_long"].timestamp,
        ))
        c = result[0]
        assert len(c.explain) >= 3
        assert any("broke" in b.lower() or "breakout" in b.lower() for b in c.explain)
        assert any("opening range" in b.lower() or "range" in b.lower() for b in c.explain)
        assert any("risk" in b.lower() or "1r" in b.lower() for b in c.explain)

    def test_valid_until_is_rth_close_utc(self):
        seq = make_rth_bar_sequence(or_high=5410.00, or_low=5400.00)
        s = ORB5mStrategy()
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"]],
            timestamp=seq["breakout_long"].timestamp,
        ))
        c = result[0]
        expected_close_et = datetime(
            SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day,
            16, 0, tzinfo=ET,
        )
        expected_close_utc = expected_close_et.astimezone(timezone.utc)
        assert c.valid_until == expected_close_utc

    def test_tags(self):
        seq = make_rth_bar_sequence(or_high=5410.00, or_low=5400.00)
        s = ORB5mStrategy()
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"]],
            timestamp=seq["breakout_long"].timestamp,
        ))
        c = result[0]
        assert c.tags["strategy"] == "orb_5m"
        assert c.tags["setup"] == "breakout_long"
        assert c.strategy == "orb_5m"
        assert c.symbol == "ESH26"

    def test_short_tags(self):
        seq = make_rth_bar_sequence(or_high=5410.00, or_low=5400.00)
        s = ORB5mStrategy()
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_short"]],
            timestamp=seq["breakout_short"].timestamp,
        ))
        assert result[0].tags["setup"] == "breakout_short"

    def test_created_at_matches_timestamp(self):
        seq = make_rth_bar_sequence(or_high=5410.00, or_low=5400.00)
        s = ORB5mStrategy()
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"]],
            timestamp=seq["breakout_long"].timestamp,
        ))
        assert result[0].created_at == seq["breakout_long"].timestamp


# ---------------------------------------------------------------------------
# Phase 5: Filters
# ---------------------------------------------------------------------------


class TestFilters:
    def test_range_below_min_no_candidates(self):
        or_range = 3 * ES_SPEC.tick_size
        or_low = 5400.00
        or_high = or_low + or_range
        seq = make_rth_bar_sequence(or_high=or_high, or_low=or_low)
        s = ORB5mStrategy(min_range_ticks=4)
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"]],
            timestamp=seq["breakout_long"].timestamp,
        ))
        assert result == []

    def test_range_above_max_no_candidates(self):
        or_range = 50 * ES_SPEC.tick_size
        or_low = 5400.00
        or_high = or_low + or_range
        seq = make_rth_bar_sequence(or_high=or_high, or_low=or_low)
        s = ORB5mStrategy(max_range_ticks=40)
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"]],
            timestamp=seq["breakout_long"].timestamp,
        ))
        assert result == []

    def test_range_at_min_boundary_passes(self):
        or_range = 4 * ES_SPEC.tick_size
        or_low = 5400.00
        or_high = or_low + or_range
        seq = make_rth_bar_sequence(or_high=or_high, or_low=or_low)
        s = ORB5mStrategy(min_range_ticks=4)
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"]],
            timestamp=seq["breakout_long"].timestamp,
        ))
        assert len(result) == 1

    def test_range_at_max_boundary_passes(self):
        or_range = 40 * ES_SPEC.tick_size
        or_low = 5400.00
        or_high = or_low + or_range
        seq = make_rth_bar_sequence(or_high=or_high, or_low=or_low)
        s = ORB5mStrategy(max_range_ticks=40)
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"]],
            timestamp=seq["breakout_long"].timestamp,
        ))
        assert len(result) == 1

    def test_custom_filter_thresholds(self):
        or_range = 8 * ES_SPEC.tick_size
        or_low = 5400.00
        or_high = or_low + or_range
        seq = make_rth_bar_sequence(or_high=or_high, or_low=or_low)
        s = ORB5mStrategy(min_range_ticks=10, max_range_ticks=20)
        s.evaluate(_ctx([seq["or_bar"]], timestamp=seq["or_bar"].timestamp))
        result = s.evaluate(_ctx(
            [seq["or_bar"], seq["breakout_long"]],
            timestamp=seq["breakout_long"].timestamp,
        ))
        assert result == []


# ---------------------------------------------------------------------------
# Phase 6: Engine integration
# ---------------------------------------------------------------------------


class TestEngineIntegration:
    def test_full_session_through_engine(self):
        from engine.config import EngineConfig
        from engine.engine import Engine
        from state.market_state import MarketState

        state = MarketState(specs={"ESH26": ES_SPEC})
        strategy = ORB5mStrategy()
        eng = Engine(
            strategies=[strategy],
            state=state,
            config=EngineConfig(eval_timeframe="5m"),
        )

        seq = make_rth_bar_sequence(or_high=5410.00, or_low=5400.00)

        result_pre = eng.on_bar(seq["premarket"])
        assert result_pre == []

        result_or = eng.on_bar(seq["or_bar"])
        assert result_or == []

        result_inside = eng.on_bar(seq["inside"])
        assert result_inside == []

        result_long = eng.on_bar(seq["breakout_long"])
        assert len(result_long) == 1
        assert result_long[0].direction == Direction.LONG
        assert result_long[0].strategy == "orb_5m"
        assert result_long[0].entry_type == EntryType.STOP

        result_dup = eng.on_bar(seq["second_long"])
        assert result_dup == []

        active = eng.get_active_candidates(now=seq["breakout_long"].timestamp)
        assert len(active) == 1

    def test_no_breakout_session(self):
        from engine.config import EngineConfig
        from engine.engine import Engine
        from state.market_state import MarketState

        state = MarketState(specs={"ESH26": ES_SPEC})
        strategy = ORB5mStrategy()
        eng = Engine(
            strategies=[strategy],
            state=state,
            config=EngineConfig(eval_timeframe="5m"),
        )

        seq = make_rth_bar_sequence(or_high=5410.00, or_low=5400.00)
        eng.on_bar(seq["or_bar"])
        result = eng.on_bar(seq["inside"])
        assert result == []
        assert eng.get_active_candidates(
            now=seq["inside"].timestamp,
        ) == []
