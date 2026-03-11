"""Tests for MarketState — quote tracking, bar windows, context/snapshot generation."""

from __future__ import annotations

from datetime import datetime, timezone

from core.market_data import Bar, DataQuality, Quote
from core.portfolio import Position, PortfolioState
from state.market_state import MarketState

from .conftest import ES_SPEC, T0, T1, T2


# ---------------------------------------------------------------------------
# Phase 2: Quote tracking
# ---------------------------------------------------------------------------


class TestMarketStateConstructor:
    def test_default_max_window_size(self):
        ms = MarketState()
        assert ms._max_window_size == 500

    def test_custom_max_window_size(self):
        ms = MarketState(max_window_size=100)
        assert ms._max_window_size == 100

    def test_default_specs_empty(self):
        ms = MarketState()
        ctx = ms.get_context(timestamp=T0)
        assert ctx.specs == {}

    def test_specs_stored_and_propagated(self):
        ms = MarketState(specs={"ESH26": ES_SPEC})
        ctx = ms.get_context(timestamp=T0)
        assert "ESH26" in ctx.specs
        assert ctx.specs["ESH26"].tick_size == 0.25

    def test_specs_in_snapshot(self):
        ms = MarketState(specs={"ESH26": ES_SPEC})
        snap = ms.get_snapshot(timestamp=T0)
        assert "ESH26" in snap.specs
        assert snap.specs["ESH26"].point_value == 50.0


class TestQuoteTracking:
    def test_update_and_retrieve_quote(self, es_quote: Quote):
        ms = MarketState()
        ms.update_quote(es_quote)
        assert ms.get_latest_quote("ESH26") is es_quote

    def test_unknown_symbol_returns_none(self):
        ms = MarketState()
        assert ms.get_latest_quote("ESH26") is None

    def test_update_same_symbol_replaces(self, es_quote: Quote):
        ms = MarketState()
        ms.update_quote(es_quote)

        updated = Quote(
            symbol="ESH26",
            bid=5410.00,
            ask=5410.25,
            last=5410.00,
            bid_size=100,
            ask_size=90,
            volume=1_300_000,
            timestamp=T1,
            source="sim",
            quality=DataQuality.OK,
        )
        ms.update_quote(updated)
        assert ms.get_latest_quote("ESH26") is updated

    def test_multiple_symbols(self, es_quote: Quote, nq_quote: Quote):
        ms = MarketState()
        ms.update_quote(es_quote)
        ms.update_quote(nq_quote)
        assert ms.get_latest_quote("ESH26") is es_quote
        assert ms.get_latest_quote("NQH26") is nq_quote


# ---------------------------------------------------------------------------
# Phase 3: Rolling bar windows
# ---------------------------------------------------------------------------


def _make_bar(symbol: str, timeframe: str, ts: datetime, close: float) -> Bar:
    return Bar(
        symbol=symbol,
        timeframe=timeframe,
        open=close - 1.0,
        high=close + 2.0,
        low=close - 2.0,
        close=close,
        volume=10_000,
        timestamp=ts,
        source="sim",
        quality=DataQuality.OK,
    )


class TestBarWindows:
    def test_update_and_get_bars(self, es_bar: Bar):
        ms = MarketState()
        ms.update_bar(es_bar)
        bars = ms.get_bars("ESH26", "5m", 10)
        assert len(bars) == 1
        assert bars[0] is es_bar

    def test_get_bars_unknown_symbol(self):
        ms = MarketState()
        assert ms.get_bars("ESH26", "5m", 10) == []

    def test_get_bars_unknown_timeframe(self, es_bar: Bar):
        ms = MarketState()
        ms.update_bar(es_bar)
        assert ms.get_bars("ESH26", "1m", 10) == []

    def test_bars_ordered_oldest_first(self):
        ms = MarketState()
        b0 = _make_bar("ESH26", "5m", T0, 5400.0)
        b1 = _make_bar("ESH26", "5m", T1, 5405.0)
        b2 = _make_bar("ESH26", "5m", T2, 5410.0)
        ms.update_bar(b0)
        ms.update_bar(b1)
        ms.update_bar(b2)
        bars = ms.get_bars("ESH26", "5m", 10)
        assert bars == [b0, b1, b2]

    def test_get_bars_count_limits_result(self):
        ms = MarketState()
        for i in range(10):
            ts = datetime(2026, 2, 24, 14, 30 + i, tzinfo=timezone.utc)
            ms.update_bar(_make_bar("ESH26", "1m", ts, 5400.0 + i))
        bars = ms.get_bars("ESH26", "1m", 3)
        assert len(bars) == 3
        assert bars[0].close == 5407.0
        assert bars[2].close == 5409.0

    def test_get_bars_count_exceeds_available(self):
        ms = MarketState()
        ms.update_bar(_make_bar("ESH26", "5m", T0, 5400.0))
        ms.update_bar(_make_bar("ESH26", "5m", T1, 5405.0))
        bars = ms.get_bars("ESH26", "5m", 100)
        assert len(bars) == 2

    def test_window_rolls_at_max_capacity(self):
        ms = MarketState(max_window_size=5)
        for i in range(8):
            ts = datetime(2026, 2, 24, 14, i, tzinfo=timezone.utc)
            ms.update_bar(_make_bar("ESH26", "5m", ts, 5400.0 + i))
        bars = ms.get_bars("ESH26", "5m", 10)
        assert len(bars) == 5
        assert bars[0].close == 5403.0
        assert bars[4].close == 5407.0

    def test_multiple_symbols_and_timeframes(self):
        ms = MarketState()
        ms.update_bar(_make_bar("ESH26", "5m", T0, 5400.0))
        ms.update_bar(_make_bar("ESH26", "1m", T0, 5401.0))
        ms.update_bar(_make_bar("NQH26", "5m", T0, 19500.0))
        assert len(ms.get_bars("ESH26", "5m", 10)) == 1
        assert len(ms.get_bars("ESH26", "1m", 10)) == 1
        assert len(ms.get_bars("NQH26", "5m", 10)) == 1
        assert ms.get_bars("NQH26", "1m", 10) == []


# ---------------------------------------------------------------------------
# Phase 4: Context / snapshot generation and isolation
# ---------------------------------------------------------------------------


class TestGetContext:
    def test_context_contains_quotes_and_bars(self, es_quote: Quote, es_bar: Bar):
        ms = MarketState()
        ms.update_quote(es_quote)
        ms.update_bar(es_bar)
        ctx = ms.get_context(timestamp=T0)
        assert ctx.timestamp == T0
        assert ctx.quotes["ESH26"] is es_quote
        assert len(ctx.bars["ESH26"]["5m"]) == 1

    def test_context_explicit_timestamp(self, es_quote: Quote):
        ms = MarketState()
        ms.update_quote(es_quote)
        ctx = ms.get_context(timestamp=T1)
        assert ctx.timestamp == T1

    def test_context_default_timestamp_is_utc_now(self, es_quote: Quote):
        ms = MarketState()
        ms.update_quote(es_quote)
        before = datetime.now(timezone.utc)
        ctx = ms.get_context()
        after = datetime.now(timezone.utc)
        assert before <= ctx.timestamp <= after
        assert ctx.timestamp.tzinfo is not None

    def test_context_empty_state(self):
        ms = MarketState()
        ctx = ms.get_context(timestamp=T0)
        assert ctx.quotes == {}
        assert ctx.bars == {}

    def test_snapshot_isolation_quotes(self, es_quote: Quote, nq_quote: Quote):
        """Updates to MarketState after get_context must not affect the Context."""
        ms = MarketState()
        ms.update_quote(es_quote)
        ctx = ms.get_context(timestamp=T0)

        ms.update_quote(nq_quote)
        assert "NQH26" not in ctx.quotes
        assert len(ctx.quotes) == 1

    def test_snapshot_isolation_bars(self):
        """Bars added after get_context must not appear in previously-created Context."""
        ms = MarketState()
        b0 = _make_bar("ESH26", "5m", T0, 5400.0)
        ms.update_bar(b0)
        ctx = ms.get_context(timestamp=T0)

        b1 = _make_bar("ESH26", "5m", T1, 5405.0)
        ms.update_bar(b1)
        assert len(ctx.bars["ESH26"]["5m"]) == 1

    def test_snapshot_isolation_bar_list_identity(self):
        """The bar list in Context must not be the same object as the internal deque."""
        ms = MarketState()
        ms.update_bar(_make_bar("ESH26", "5m", T0, 5400.0))
        ctx = ms.get_context(timestamp=T0)
        internal_bars = ms.get_bars("ESH26", "5m", 10)
        assert ctx.bars["ESH26"]["5m"] is not internal_bars

    def test_get_context_with_portfolio(self):
        """When portfolio is passed, Context includes it."""
        ms = MarketState()
        pos = Position(instrument_id="ESH26", qty=1, avg_price=5400.0)
        portfolio = PortfolioState(cash=100_000.0, positions={"ESH26": pos})
        ctx = ms.get_context(timestamp=T0, portfolio=portfolio)
        assert ctx.portfolio is portfolio
        assert ctx.portfolio.positions["ESH26"].qty == 1


class TestGetSnapshot:
    def test_snapshot_contains_data(self, es_quote: Quote, es_bar: Bar):
        ms = MarketState()
        ms.update_quote(es_quote)
        ms.update_bar(es_bar)
        snap = ms.get_snapshot(timestamp=T0)
        assert snap.timestamp == T0
        assert "ESH26" in snap.quotes
        assert "ESH26" in snap.bars

    def test_snapshot_explicit_timestamp(self):
        ms = MarketState()
        snap = ms.get_snapshot(timestamp=T2)
        assert snap.timestamp == T2

    def test_snapshot_default_timestamp_is_utc_now(self):
        ms = MarketState()
        before = datetime.now(timezone.utc)
        snap = ms.get_snapshot()
        after = datetime.now(timezone.utc)
        assert before <= snap.timestamp <= after

    def test_snapshot_isolation_quotes(self, es_quote: Quote, nq_quote: Quote):
        ms = MarketState()
        ms.update_quote(es_quote)
        snap = ms.get_snapshot(timestamp=T0)

        ms.update_quote(nq_quote)
        assert "NQH26" not in snap.quotes

    def test_snapshot_isolation_bars(self):
        ms = MarketState()
        ms.update_bar(_make_bar("ESH26", "5m", T0, 5400.0))
        snap = ms.get_snapshot(timestamp=T0)

        ms.update_bar(_make_bar("ESH26", "5m", T1, 5405.0))
        assert len(snap.bars["ESH26"]["5m"]) == 1
