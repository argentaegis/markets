"""Tests for WebSocket /ws endpoint and ConnectionManager."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from api.ws_handler import ConnectionManager
from core.market_data import DataQuality, Quote


class TestWebSocketEndpoint:
    def test_connects_successfully(self, app) -> None:
        app.state.ws_manager = ConnectionManager()
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            assert ws is not None

    def test_registered_on_connect(self, app) -> None:
        manager = ConnectionManager()
        app.state.ws_manager = manager
        client = TestClient(app)
        with client.websocket_connect("/ws"):
            assert len(manager._connections) == 1

    def test_unregistered_on_disconnect(self, app) -> None:
        manager = ConnectionManager()
        app.state.ws_manager = manager
        client = TestClient(app)
        with client.websocket_connect("/ws"):
            pass
        assert len(manager._connections) == 0


class TestConnectionManager:
    """Unit tests for ConnectionManager using mock WebSockets."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_connect_adds_to_list(self) -> None:
        manager = ConnectionManager()
        ws = AsyncMock()

        async def _test():
            await manager.connect(ws)
            assert len(manager._connections) == 1

        self._run(_test())

    def test_disconnect_removes_from_list(self) -> None:
        manager = ConnectionManager()
        ws = AsyncMock()

        async def _test():
            await manager.connect(ws)
            manager.disconnect(ws)
            assert len(manager._connections) == 0

        self._run(_test())

    def test_broadcast_sends_json_to_client(self) -> None:
        manager = ConnectionManager()
        ws = AsyncMock()

        quote = Quote(
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

        async def _test():
            await manager.connect(ws)
            await manager.broadcast("quote_update", quote)

            ws.send_json.assert_called_once()
            payload = ws.send_json.call_args[0][0]
            assert payload["type"] == "quote_update"
            assert payload["data"]["symbol"] == "ESH26"
            assert payload["data"]["bid"] == 5400.0

        self._run(_test())

    def test_broadcast_message_format(self) -> None:
        manager = ConnectionManager()
        ws = AsyncMock()

        quote = Quote(
            symbol="NQM26",
            bid=19500.0,
            ask=19500.25,
            last=19500.0,
            bid_size=50,
            ask_size=60,
            volume=30000,
            timestamp=datetime(2026, 2, 24, 14, 30, 0, tzinfo=timezone.utc),
            source="sim",
            quality=DataQuality.OK,
        )

        async def _test():
            await manager.connect(ws)
            await manager.broadcast("quote_update", quote)

            payload = ws.send_json.call_args[0][0]
            assert set(payload.keys()) == {"type", "data"}
            assert isinstance(payload["data"], dict)

        self._run(_test())

    def test_broadcast_candidates_as_list(self, sample_candidate) -> None:
        manager = ConnectionManager()
        ws = AsyncMock()

        async def _test():
            await manager.connect(ws)
            await manager.broadcast("candidates_update", [sample_candidate])

            payload = ws.send_json.call_args[0][0]
            assert payload["type"] == "candidates_update"
            assert isinstance(payload["data"], list)
            assert len(payload["data"]) == 1
            assert payload["data"][0]["symbol"] == "ESH26"

        self._run(_test())

    def test_broadcast_to_multiple_clients(self) -> None:
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        quote = Quote(
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

        async def _test():
            await manager.connect(ws1)
            await manager.connect(ws2)
            await manager.broadcast("quote_update", quote)

            assert ws1.send_json.call_count == 1
            assert ws2.send_json.call_count == 1

        self._run(_test())

    def test_dead_client_removed_silently(self) -> None:
        manager = ConnectionManager()
        ws_good = AsyncMock()
        ws_dead = AsyncMock()
        ws_dead.send_json.side_effect = RuntimeError("connection closed")

        quote = Quote(
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

        async def _test():
            await manager.connect(ws_good)
            await manager.connect(ws_dead)
            assert len(manager._connections) == 2

            await manager.broadcast("quote_update", quote)

            assert len(manager._connections) == 1
            assert ws_good in manager._connections

        self._run(_test())
