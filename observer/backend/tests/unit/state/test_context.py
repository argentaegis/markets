"""Tests for Context and MarketSnapshot types.

Covers frozen enforcement, field access, empty state, and specs propagation.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.instrument import ContractSpec, InstrumentType, TradingSession
from core.market_data import Bar, DataQuality, Quote
from core.portfolio import Position, PortfolioState, create_mock_portfolio
from state.context import Context, MarketSnapshot

from .conftest import ES_SPEC

NOW_UTC = datetime(2026, 2, 24, 14, 35, 0, tzinfo=timezone.utc)


def _sample_quote() -> Quote:
    return Quote(
        symbol="ESH26",
        bid=5400.25,
        ask=5400.50,
        last=5400.25,
        bid_size=120,
        ask_size=85,
        volume=1_200_000,
        timestamp=NOW_UTC,
        source="sim",
        quality=DataQuality.OK,
    )


def _sample_bar() -> Bar:
    return Bar(
        symbol="ESH26",
        timeframe="5m",
        open=5400.00,
        high=5405.25,
        low=5398.50,
        close=5403.75,
        volume=45_000,
        timestamp=NOW_UTC,
        source="sim",
        quality=DataQuality.OK,
    )


class TestContext:
    def test_creation(self):
        ctx = Context(
            timestamp=NOW_UTC,
            quotes={"ESH26": _sample_quote()},
            bars={"ESH26": {"5m": [_sample_bar()]}},
        )
        assert ctx.timestamp == NOW_UTC
        assert "ESH26" in ctx.quotes
        assert "ESH26" in ctx.bars
        assert len(ctx.bars["ESH26"]["5m"]) == 1

    def test_frozen_field_reassignment_raises(self):
        ctx = Context(timestamp=NOW_UTC, quotes={}, bars={})
        with pytest.raises(AttributeError):
            ctx.timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_frozen_quotes_reassignment_raises(self):
        ctx = Context(timestamp=NOW_UTC, quotes={}, bars={})
        with pytest.raises(AttributeError):
            ctx.quotes = {"ESH26": _sample_quote()}

    def test_empty_context(self):
        ctx = Context(timestamp=NOW_UTC, quotes={}, bars={})
        assert ctx.quotes == {}
        assert ctx.bars == {}

    def test_specs_default_empty_dict(self):
        ctx = Context(timestamp=NOW_UTC, quotes={}, bars={})
        assert ctx.specs == {}

    def test_creation_with_specs(self):
        ctx = Context(
            timestamp=NOW_UTC,
            quotes={},
            bars={},
            specs={"ESH26": ES_SPEC},
        )
        assert "ESH26" in ctx.specs
        assert ctx.specs["ESH26"].tick_size == 0.25

    def test_frozen_specs_reassignment_raises(self):
        ctx = Context(timestamp=NOW_UTC, quotes={}, bars={})
        with pytest.raises(AttributeError):
            ctx.specs = {"ESH26": ES_SPEC}

    def test_portfolio_defaults_to_mock(self):
        ctx = Context(timestamp=NOW_UTC, quotes={}, bars={})
        assert ctx.portfolio.cash == 0.0
        assert ctx.portfolio.positions == {}

    def test_creation_with_portfolio(self):
        pos = Position(instrument_id="ESH26", qty=1, avg_price=5400.0)
        portfolio = PortfolioState(cash=100_000.0, positions={"ESH26": pos})
        ctx = Context(
            timestamp=NOW_UTC,
            quotes={},
            bars={},
            portfolio=portfolio,
        )
        assert ctx.portfolio is portfolio
        assert ctx.portfolio.positions["ESH26"].qty == 1


class TestMarketSnapshot:
    def test_creation(self):
        snap = MarketSnapshot(
            timestamp=NOW_UTC,
            quotes={"ESH26": _sample_quote()},
            bars={"ESH26": {"5m": [_sample_bar()]}},
        )
        assert snap.timestamp == NOW_UTC
        assert "ESH26" in snap.quotes
        assert len(snap.bars["ESH26"]["5m"]) == 1

    def test_not_frozen(self):
        snap = MarketSnapshot(timestamp=NOW_UTC, quotes={}, bars={})
        snap.timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert snap.timestamp.year == 2026

    def test_specs_default_empty_dict(self):
        snap = MarketSnapshot(timestamp=NOW_UTC, quotes={}, bars={})
        assert snap.specs == {}

    def test_creation_with_specs(self):
        snap = MarketSnapshot(
            timestamp=NOW_UTC,
            quotes={},
            bars={},
            specs={"ESH26": ES_SPEC},
        )
        assert snap.specs["ESH26"].point_value == 50.0
