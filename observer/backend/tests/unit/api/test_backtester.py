"""Unit tests for backtester API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.backtester import router as backtester_router
from fastapi import FastAPI


def _create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(backtester_router)
    return app


def test_get_configs_returns_list() -> None:
    app = _create_app()
    with TestClient(app) as client:
        resp = client.get("/api/backtester/configs")
        assert resp.status_code == 200
        data = resp.json()
        assert "configs" in data
        assert isinstance(data["configs"], list)
        if data["configs"]:
            c = data["configs"][0]
            assert "name" in c
            assert "path" in c
            assert "label" in c
            assert c["path"].startswith("backtester/configs/")


def test_run_rejects_invalid_path() -> None:
    app = _create_app()
    with TestClient(app) as client:
        resp = client.post("/api/backtester/runs", json={"config_path": "../etc/passwd"})
        assert resp.status_code == 400
