"""Pytest fixtures for portfolio tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


@pytest.fixture
def sample_ts() -> datetime:
    return datetime(2026, 1, 15, 14, 35, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_contract_id() -> str:
    return "SPY|2026-03-20|C|485|100"


@pytest.fixture
def sample_symbol() -> str:
    return "SPY"
