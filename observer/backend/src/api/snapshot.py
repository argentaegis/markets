"""GET /api/snapshot — current market state + active candidates."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from api.serializers import serialize_snapshot

router = APIRouter()


@router.get("/api/snapshot")
async def get_snapshot(request: Request) -> dict[str, Any]:
    state = request.app.state.market_state
    engine = request.app.state.engine
    snapshot = state.get_snapshot()
    candidates = engine.get_active_candidates()
    return serialize_snapshot(snapshot, candidates)
