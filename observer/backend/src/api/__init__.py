"""Backend API — FastAPI endpoints, WebSocket handler, wiring."""

from .app import create_app

__all__ = ["create_app"]
