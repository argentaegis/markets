"""Integration tests — full pipeline via the live app.

These tests use a real SimProvider with fast intervals so messages
arrive within a short timeout window.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.ws_handler import ConnectionManager, router as ws_router
from api.snapshot import router as snapshot_router
from api.health import router as health_router
from api.wiring import consume_bars, consume_quotes
from config import AppConfig, StrategyEntry, load_config
from engine.engine import Engine
from providers.sim_provider import SimProvider
from state.market_state import MarketState
from strategies.registry import StrategyRegistry


def _create_fast_app() -> FastAPI:
    """App wired with a fast-ticking SimProvider for integration tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        provider = SimProvider(
            seed=42,
            quote_interval=0.01,
            bar_interval=0.05,
        )
        await provider.connect()
        specs = provider.get_contract_specs()

        cfg = AppConfig(strategies={"dummy": StrategyEntry(enabled=True)})
        registry = StrategyRegistry()
        strategies = registry.instantiate(cfg)

        state = MarketState(specs=specs)
        engine = Engine(
            strategies=strategies,
            state=state,
            config=cfg.engine,
        )
        ws_manager = ConnectionManager()

        symbols = list(specs.keys())
        timeframe = engine._config.eval_timeframe

        quote_task = asyncio.create_task(
            consume_quotes(provider, symbols, state, ws_manager)
        )
        bar_task = asyncio.create_task(
            consume_bars(provider, symbols, timeframe, engine, ws_manager)
        )

        app.state.provider = provider
        app.state.market_state = state
        app.state.engine = engine
        app.state.ws_manager = ws_manager

        yield

        quote_task.cancel()
        bar_task.cancel()
        await provider.disconnect()

    app = FastAPI(title="Observer-Test", lifespan=lifespan)
    app.include_router(snapshot_router)
    app.include_router(health_router)
    app.include_router(ws_router)
    return app


class TestFullPipeline:
    def test_health_returns_connected(self) -> None:
        app = _create_fast_app()
        with TestClient(app) as client:
            resp = client.get("/api/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["provider"]["connected"] is True

    def test_snapshot_populates_after_startup(self) -> None:
        app = _create_fast_app()
        with TestClient(app) as client:
            import time
            time.sleep(0.2)
            resp = client.get("/api/snapshot")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["quotes"]) > 0 or len(data["bars"]) > 0

    def test_websocket_receives_quote_update(self) -> None:
        app = _create_fast_app()
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as ws:
                msg = ws.receive_json(mode="text")
                assert msg["type"] in ("quote_update", "bar_update", "candidates_update")
                assert "data" in msg

    def test_websocket_receives_bar_update(self) -> None:
        app = _create_fast_app()
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as ws:
                seen_bar = False
                for _ in range(50):
                    msg = ws.receive_json(mode="text")
                    if msg["type"] == "bar_update":
                        seen_bar = True
                        assert "symbol" in msg["data"]
                        assert "timeframe" in msg["data"]
                        break
                assert seen_bar, "No bar_update received within 50 messages"

    def test_websocket_receives_candidates_after_bar(self) -> None:
        app = _create_fast_app()
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as ws:
                seen_candidates = False
                for _ in range(100):
                    msg = ws.receive_json(mode="text")
                    if msg["type"] == "candidates_update":
                        seen_candidates = True
                        assert isinstance(msg["data"], list)
                        assert len(msg["data"]) >= 1
                        assert msg["data"][0]["strategy"] == "dummy"
                        break
                assert seen_candidates, "No candidates_update received within 100 messages"
