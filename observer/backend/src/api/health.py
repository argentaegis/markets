"""GET /api/health — backend + provider health."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/api/health")
async def get_health(request: Request) -> dict[str, Any]:
    provider = request.app.state.provider
    health = await provider.health()

    return {
        "status": "ok",
        "provider": {
            "connected": health.connected,
            "source": health.source,
            "last_heartbeat": health.last_heartbeat.isoformat() if health.last_heartbeat else None,
            "message": health.message,
        },
    }
