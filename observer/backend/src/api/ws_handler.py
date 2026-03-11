"""WebSocket connection manager + /ws endpoint."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from api.serializers import serialize_bar, serialize_candidate, serialize_quote

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Tracks connected WebSocket clients and broadcasts messages."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)
        logger.info("WebSocket client connected (%d total)", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.remove(websocket)
        logger.info("WebSocket client disconnected (%d total)", len(self._connections))

    async def broadcast(self, msg_type: str, data: Any) -> None:
        payload = {"type": msg_type, "data": _serialize_data(data)}
        dead: list[WebSocket] = []

        for ws in self._connections:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            try:
                self._connections.remove(ws)
            except ValueError:
                pass


def _serialize_data(data: Any) -> Any:
    """Convert core dataclasses to JSON-safe dicts."""
    from core.market_data import Bar, Quote
    from core.candidate import TradeCandidate

    if isinstance(data, Quote):
        return serialize_quote(data)
    if isinstance(data, Bar):
        return serialize_bar(data)
    if isinstance(data, list):
        return [_serialize_data(item) for item in data]
    if isinstance(data, TradeCandidate):
        return serialize_candidate(data)
    return data


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    manager: ConnectionManager = websocket.app.state.ws_manager
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
