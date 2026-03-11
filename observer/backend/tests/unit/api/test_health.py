"""Tests for GET /api/health."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from providers.base import ProviderHealth


class _FakeProvider:
    """Minimal provider that only implements health()."""

    def __init__(self, connected: bool = True) -> None:
        self._connected = connected

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            connected=self._connected,
            source="fake",
            last_heartbeat=datetime(2026, 2, 24, 14, 30, 0, tzinfo=timezone.utc),
            message="OK" if self._connected else "Disconnected",
        )


class TestHealthEndpoint:
    def test_returns_200(self, app) -> None:
        app.state.provider = _FakeProvider(connected=True)
        client = TestClient(app)
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_response_has_expected_keys(self, app) -> None:
        app.state.provider = _FakeProvider(connected=True)
        client = TestClient(app)
        data = client.get("/api/health").json()
        assert "status" in data
        assert "provider" in data

    def test_status_ok_when_connected(self, app) -> None:
        app.state.provider = _FakeProvider(connected=True)
        client = TestClient(app)
        data = client.get("/api/health").json()
        assert data["status"] == "ok"

    def test_provider_health_fields(self, app) -> None:
        app.state.provider = _FakeProvider(connected=True)
        client = TestClient(app)
        data = client.get("/api/health").json()
        prov = data["provider"]
        assert prov["connected"] is True
        assert prov["source"] == "fake"
        assert "last_heartbeat" in prov
        assert prov["message"] == "OK"

    def test_disconnected_provider(self, app) -> None:
        app.state.provider = _FakeProvider(connected=False)
        client = TestClient(app)
        data = client.get("/api/health").json()
        assert data["provider"]["connected"] is False
        assert data["provider"]["message"] == "Disconnected"
