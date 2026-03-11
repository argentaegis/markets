"""Tests for SchwabProvider — mocked httpx REST API calls."""

from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from providers.schwab_provider import SchwabProvider


def _make_token_file(tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text(json.dumps({
        "creation_timestamp": int(time.time()),
        "token": {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 1800,
            "token_type": "Bearer",
            "scope": "api",
        },
    }))
    return str(token_path)


def _make_provider(tmp_path, **overrides) -> SchwabProvider:
    defaults = dict(
        api_key="test-key",
        app_secret="test-secret",
        token_path=_make_token_file(tmp_path),
    )
    defaults.update(overrides)
    return SchwabProvider(**defaults)


def _mock_quotes_response():
    return {
        "/ESH26": {
            "quote": {
                "bidPrice": 5400.25,
                "askPrice": 5400.50,
                "lastPrice": 5400.25,
                "bidSize": 120,
                "askSize": 85,
                "totalVolume": 1200000,
                "quoteTime": 1740408600000,
                "securityStatus": "Normal",
                "futureActiveSymbol": "/ESH26",
            },
            "reference": {},
        },
    }


def _mock_price_history_response():
    return {
        "candles": [
            {
                "datetime": 1740408300000,
                "open": 5400.0,
                "high": 5405.0,
                "low": 5398.0,
                "close": 5403.0,
                "volume": 10000,
            },
            {
                "datetime": 1740408600000,
                "open": 5403.0,
                "high": 5408.0,
                "low": 5401.0,
                "close": 5406.0,
                "volume": 12000,
            },
        ],
    }


class TestInit:
    def test_accepts_credential_params(self, tmp_path):
        provider = _make_provider(tmp_path)
        assert provider._api_key == "test-key"

    def test_default_symbols(self, tmp_path):
        provider = _make_provider(tmp_path)
        assert len(provider._symbols) > 0

    def test_custom_symbols(self, tmp_path):
        provider = _make_provider(tmp_path, symbols=["ESH26"])
        assert provider._symbols == ["ESH26"]


class TestGetContractSpecs:
    def test_returns_specs_before_connect(self, tmp_path):
        provider = _make_provider(tmp_path)
        specs = provider.get_contract_specs()
        assert "ESH26" in specs
        assert specs["ESH26"].tick_size == 0.25
        assert specs["ESH26"].point_value == 50.0

    def test_returns_custom_symbol_specs(self, tmp_path):
        provider = _make_provider(tmp_path, symbols=["ESH26"])
        specs = provider.get_contract_specs()
        assert "ESH26" in specs


class TestConnect:
    def test_connect_validates_and_sets_connected(self, tmp_path):
        provider = _make_provider(tmp_path)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_quotes_response()

        async def _run():
            with patch("providers.schwab_provider.httpx.AsyncClient") as MockClient:
                instance = AsyncMock()
                instance.get.return_value = mock_response
                MockClient.return_value = instance
                await provider.connect()
                assert provider._connected is True

        asyncio.run(_run())

    def test_connect_failure_raises(self, tmp_path):
        provider = _make_provider(tmp_path)

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        async def _run():
            with patch("providers.schwab_provider.httpx.AsyncClient") as MockClient:
                instance = AsyncMock()
                instance.get.return_value = mock_response
                MockClient.return_value = instance
                with pytest.raises(ConnectionError):
                    await provider.connect()

        asyncio.run(_run())

    def test_missing_token_file_raises(self, tmp_path):
        provider = SchwabProvider(
            api_key="k", app_secret="s",
            token_path=str(tmp_path / "nonexistent.json"),
        )
        with pytest.raises(FileNotFoundError):
            asyncio.run(provider.connect())


class TestDisconnect:
    def test_disconnect_cleans_up(self, tmp_path):
        provider = _make_provider(tmp_path)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_quotes_response()

        async def _run():
            with patch("providers.schwab_provider.httpx.AsyncClient") as MockClient:
                instance = AsyncMock()
                instance.get.return_value = mock_response
                MockClient.return_value = instance
                await provider.connect()
                await provider.disconnect()
                assert provider._connected is False

        asyncio.run(_run())


class TestHealth:
    def test_health_before_connect(self, tmp_path):
        provider = _make_provider(tmp_path)
        health = asyncio.run(provider.health())
        assert health.connected is False
        assert health.source == "schwab"
        assert health.message == "Disconnected"


class TestParseQuote:
    def test_parses_rest_quote(self, tmp_path):
        provider = _make_provider(tmp_path)
        quote = provider._parse_quote("/ESH26", _mock_quotes_response()["/ESH26"])
        assert quote is not None
        assert quote.symbol == "ESH26"
        assert quote.bid == 5400.25
        assert quote.ask == 5400.50
        assert quote.last == 5400.25
        assert quote.bid_size == 120
        assert quote.ask_size == 85
        assert quote.volume == 1200000
        assert quote.source == "schwab"
        assert quote.quality.value == "OK"

    def test_handles_missing_fields(self, tmp_path):
        provider = _make_provider(tmp_path)
        quote = provider._parse_quote("/ESH26", {"quote": {}, "reference": {}})
        assert quote is not None
        assert quote.last == 0


class TestParseBars:
    def test_parses_candles(self, tmp_path):
        provider = _make_provider(tmp_path)
        bars = provider._parse_bars("ESH26", "5m", _mock_price_history_response())
        assert len(bars) == 2
        assert bars[0].symbol == "ESH26"
        assert bars[0].timeframe == "5m"
        assert bars[0].open == 5400.0
        assert bars[0].high == 5405.0
        assert bars[0].close == 5403.0
        assert bars[0].volume == 10000
        assert bars[0].source == "schwab"

    def test_deduplicates_on_subsequent_calls(self, tmp_path):
        provider = _make_provider(tmp_path)
        data = _mock_price_history_response()
        bars1 = provider._parse_bars("ESH26", "5m", data)
        assert len(bars1) == 2
        bars2 = provider._parse_bars("ESH26", "5m", data)
        assert len(bars2) == 0

    def test_empty_candles(self, tmp_path):
        provider = _make_provider(tmp_path)
        bars = provider._parse_bars("ESH26", "5m", {"candles": []})
        assert bars == []


class TestProviderSelection:
    def test_schwab_with_credentials(self, tmp_path):
        env = {
            "OBSERVER_PROVIDER": "schwab",
            "SCHWAB_API_KEY": "test-key",
            "SCHWAB_APP_SECRET": "test-secret",
            "SCHWAB_TOKEN_PATH": _make_token_file(tmp_path),
        }
        import os
        with patch.dict(os.environ, env, clear=True):
            from api.app import _create_provider
            provider = _create_provider()
            assert isinstance(provider, SchwabProvider)

    def test_schwab_missing_credentials_raises(self):
        import os
        env = {"OBSERVER_PROVIDER": "schwab"}
        with patch.dict(os.environ, env, clear=True):
            from api.app import _create_provider
            with pytest.raises(ValueError, match="SCHWAB_API_KEY"):
                _create_provider()
