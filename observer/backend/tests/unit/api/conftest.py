"""Shared fixtures for API unit tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.candidate import Direction, EntryType, TradeCandidate
from core.market_data import Bar, DataQuality, Quote
from engine.config import EngineConfig
from engine.engine import Engine
from state.market_state import MarketState
from strategies.dummy_strategy import DummyStrategy


@pytest.fixture()
def app():
    """Bare app with no state attached (for router-level tests)."""
    return create_app()


@pytest.fixture()
def populated_app(app):
    """App with pre-populated MarketState, Engine, and a mock provider.

    Uses current time so candidates created by DummyStrategy (valid_until =
    timestamp + 5 minutes) are still active when the endpoint reads them.
    """
    state = MarketState()
    engine = Engine(
        strategies=[DummyStrategy()],
        state=state,
        config=EngineConfig(),
    )

    now = datetime.now(timezone.utc)

    quote = Quote(
        symbol="ESH26",
        bid=5400.0,
        ask=5400.25,
        last=5400.0,
        bid_size=100,
        ask_size=120,
        volume=50000,
        timestamp=now,
        source="sim",
        quality=DataQuality.OK,
    )
    state.update_quote(quote)

    bar = Bar(
        symbol="ESH26",
        timeframe="5m",
        open=5400.0,
        high=5402.0,
        low=5398.0,
        close=5401.0,
        volume=1200,
        timestamp=now,
        source="sim",
        quality=DataQuality.OK,
    )
    engine.on_bar(bar)

    app.state.market_state = state
    app.state.engine = engine

    return app


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture()
def populated_client(populated_app) -> TestClient:
    return TestClient(populated_app)


@pytest.fixture()
def sample_quote() -> Quote:
    return Quote(
        symbol="ESH26",
        bid=5400.0,
        ask=5400.25,
        last=5400.0,
        bid_size=100,
        ask_size=120,
        volume=50000,
        timestamp=datetime(2026, 2, 24, 14, 30, 0, tzinfo=timezone.utc),
        source="sim",
        quality=DataQuality.OK,
    )


@pytest.fixture()
def sample_bar() -> Bar:
    return Bar(
        symbol="ESH26",
        timeframe="5m",
        open=5400.0,
        high=5402.0,
        low=5398.0,
        close=5401.0,
        volume=1200,
        timestamp=datetime(2026, 2, 24, 14, 35, 0, tzinfo=timezone.utc),
        source="sim",
        quality=DataQuality.OK,
    )


@pytest.fixture()
def sample_candidate() -> TradeCandidate:
    return TradeCandidate(
        id="test-001",
        symbol="ESH26",
        strategy="dummy",
        direction=Direction.LONG,
        entry_type=EntryType.STOP,
        entry_price=5402.0,
        stop_price=5398.0,
        targets=[5410.0, 5420.0],
        score=75.0,
        explain=["test reason"],
        valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
        tags={"tf": "5m"},
        created_at=datetime(2026, 2, 24, 14, 35, 0, tzinfo=timezone.utc),
    )
