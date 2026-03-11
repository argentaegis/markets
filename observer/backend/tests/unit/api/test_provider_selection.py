"""Tests for provider selection via OBSERVER_PROVIDER env var."""

from __future__ import annotations

import json
import os
import time
from unittest.mock import patch

from api.app import _create_provider
from providers.schwab_provider import SchwabProvider
from providers.sim_provider import SimProvider


def _make_token_file(tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text(json.dumps({
        "creation_timestamp": int(time.time()),
        "token": {
            "access_token": "test",
            "refresh_token": "test",
            "expires_in": 1800,
        },
    }))
    return str(token_path)


class TestCreateProvider:
    def test_default_is_sim(self):
        with patch.dict(os.environ, {}, clear=True):
            provider = _create_provider()
            assert isinstance(provider, SimProvider)

    def test_explicit_sim(self):
        with patch.dict(os.environ, {"OBSERVER_PROVIDER": "sim"}, clear=True):
            provider = _create_provider()
            assert isinstance(provider, SimProvider)

    def test_schwab_with_credentials(self, tmp_path):
        env = {
            "OBSERVER_PROVIDER": "schwab",
            "SCHWAB_API_KEY": "test-key",
            "SCHWAB_APP_SECRET": "test-secret",
            "SCHWAB_TOKEN_PATH": _make_token_file(tmp_path),
        }
        with patch.dict(os.environ, env, clear=True):
            provider = _create_provider()
            assert isinstance(provider, SchwabProvider)

    def test_schwab_missing_credentials_raises(self):
        env = {"OBSERVER_PROVIDER": "schwab"}
        with patch.dict(os.environ, env, clear=True):
            import pytest
            with pytest.raises(ValueError, match="SCHWAB_API_KEY"):
                _create_provider()

    def test_existing_sim_tests_unaffected(self):
        with patch.dict(os.environ, {"OBSERVER_PROVIDER": "sim"}, clear=True):
            provider = _create_provider()
            specs = provider.get_contract_specs()
            assert len(specs) > 0
