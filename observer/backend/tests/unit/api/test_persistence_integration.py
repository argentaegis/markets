"""Integration tests — persistence wiring via StateStore.

Verifies that consume_quotes and consume_bars write to StateStore
when enabled, and that the pipeline works normally when disabled.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.ws_handler import ConnectionManager, router as ws_router
from api.snapshot import router as snapshot_router
from api.health import router as health_router
from api.wiring import consume_bars, consume_quotes
from engine.config import EngineConfig
from engine.engine import Engine
from providers.sim_provider import SimProvider
from state.market_state import MarketState
from state.persistence import StateStore
from strategies.dummy_strategy import DummyStrategy


def _create_app_with_store(store: StateStore) -> FastAPI:
    """App wired with a fast-ticking SimProvider and an optional StateStore."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        provider = SimProvider(
            seed=42,
            quote_interval=0.01,
            bar_interval=0.05,
        )
        state = MarketState()
        engine = Engine(
            strategies=[DummyStrategy()],
            state=state,
            config=EngineConfig(),
        )
        ws_manager = ConnectionManager()

        await provider.connect()
        symbols = list(provider.get_contract_specs().keys())
        timeframe = engine._config.eval_timeframe

        quote_task = asyncio.create_task(
            consume_quotes(provider, symbols, state, ws_manager, store=store)
        )
        bar_task = asyncio.create_task(
            consume_bars(provider, symbols, timeframe, engine, ws_manager, store=store)
        )

        app.state.provider = provider
        app.state.market_state = state
        app.state.engine = engine
        app.state.ws_manager = ws_manager
        app.state.store = store

        yield

        quote_task.cancel()
        bar_task.cancel()
        await provider.disconnect()

    app = FastAPI(title="Observer-Test-Persistence", lifespan=lifespan)
    app.include_router(snapshot_router)
    app.include_router(health_router)
    app.include_router(ws_router)
    return app


class TestPersistenceEnabled:
    def test_quotes_persisted(self) -> None:
        store = StateStore(db_path=":memory:")
        app = _create_app_with_store(store)
        with TestClient(app):
            time.sleep(0.3)
            quotes = store.get_quotes("ESH26")
            assert len(quotes) > 0

    def test_bars_persisted(self) -> None:
        store = StateStore(db_path=":memory:")
        app = _create_app_with_store(store)
        with TestClient(app):
            time.sleep(0.3)
            bars = store.get_bars("ESH26", "5m")
            assert len(bars) > 0


class TestPersistenceDisabled:
    def test_no_error_when_disabled(self) -> None:
        store = StateStore(db_path=None)
        app = _create_app_with_store(store)
        with TestClient(app) as client:
            time.sleep(0.1)
            resp = client.get("/api/health")
            assert resp.status_code == 200
            assert store.enabled is False
