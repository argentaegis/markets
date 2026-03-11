"""Tests for BaseProvider ABC and ProviderHealth.

Covers abstract enforcement, ProviderHealth fields, and that BaseProvider
defines all 6 required methods.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from providers.base import BaseProvider, ProviderHealth


class TestBaseProviderIsAbstract:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseProvider()

    def test_defines_connect(self):
        assert hasattr(BaseProvider, "connect")

    def test_defines_subscribe_quotes(self):
        assert hasattr(BaseProvider, "subscribe_quotes")

    def test_defines_subscribe_bars(self):
        assert hasattr(BaseProvider, "subscribe_bars")

    def test_defines_disconnect(self):
        assert hasattr(BaseProvider, "disconnect")

    def test_defines_health(self):
        assert hasattr(BaseProvider, "health")

    def test_defines_get_contract_specs(self):
        assert hasattr(BaseProvider, "get_contract_specs")

    def test_has_six_abstract_methods(self):
        abstracts = getattr(BaseProvider, "__abstractmethods__", set())
        assert len(abstracts) == 6
        expected = {
            "connect",
            "subscribe_quotes",
            "subscribe_bars",
            "disconnect",
            "health",
            "get_contract_specs",
        }
        assert abstracts == expected


class TestProviderHealth:
    def test_creation(self):
        h = ProviderHealth(
            connected=True,
            source="sim",
            last_heartbeat=datetime(2026, 2, 24, 14, 0, tzinfo=timezone.utc),
            message="OK",
        )
        assert h.connected is True
        assert h.source == "sim"
        assert h.last_heartbeat is not None
        assert h.message == "OK"

    def test_immutability(self):
        h = ProviderHealth(
            connected=True,
            source="sim",
            last_heartbeat=None,
            message="OK",
        )
        with pytest.raises(AttributeError):
            h.connected = False

    def test_none_heartbeat(self):
        h = ProviderHealth(
            connected=False,
            source="schwab",
            last_heartbeat=None,
            message="Not connected",
        )
        assert h.last_heartbeat is None
        assert h.connected is False
