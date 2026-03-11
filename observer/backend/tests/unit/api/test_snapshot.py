"""Tests for GET /api/snapshot."""

from __future__ import annotations

from datetime import datetime, timezone

from core.market_data import DataQuality, Quote, Bar
from engine.config import EngineConfig
from engine.engine import Engine
from state.market_state import MarketState
from strategies.dummy_strategy import DummyStrategy


class TestSnapshotEndpoint:
    def test_returns_200_with_populated_state(self, populated_client) -> None:
        resp = populated_client.get("/api/snapshot")
        assert resp.status_code == 200

    def test_response_has_expected_keys(self, populated_client) -> None:
        resp = populated_client.get("/api/snapshot")
        data = resp.json()
        assert set(data.keys()) == {"quotes", "bars", "candidates"}

    def test_quotes_contain_populated_symbol(self, populated_client) -> None:
        data = populated_client.get("/api/snapshot").json()
        assert "ESH26" in data["quotes"]
        assert data["quotes"]["ESH26"]["bid"] == 5400.0

    def test_bars_contain_populated_data(self, populated_client) -> None:
        data = populated_client.get("/api/snapshot").json()
        assert "ESH26" in data["bars"]
        assert "5m" in data["bars"]["ESH26"]
        assert len(data["bars"]["ESH26"]["5m"]) == 1

    def test_candidates_present_after_evaluation(self, populated_client) -> None:
        data = populated_client.get("/api/snapshot").json()
        assert isinstance(data["candidates"], list)
        assert len(data["candidates"]) >= 1
        assert data["candidates"][0]["strategy"] == "dummy"

    def test_empty_state_returns_empty_collections(self, app) -> None:
        from fastapi.testclient import TestClient

        state = MarketState()
        engine = Engine(
            strategies=[DummyStrategy()],
            state=state,
            config=EngineConfig(),
        )
        app.state.market_state = state
        app.state.engine = engine

        client = TestClient(app)
        data = client.get("/api/snapshot").json()
        assert data["quotes"] == {}
        assert data["bars"] == {}
        assert data["candidates"] == []
