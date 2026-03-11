"""Shared fixtures for domain tests.

Reasoning: Domain tests need deterministic, reusable fixtures for timestamps and
identifiers. Centralizing them ensures consistency and avoids magic values scattered
across test files. UTC timestamps align with DataProvider boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


@pytest.fixture
def sample_ts() -> datetime:
    """UTC timestamp for order/fill/event tests."""
    return datetime(2026, 1, 15, 14, 35, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_contract_id() -> str:
    """Canonical contract_id format per domain/contract_id."""
    return "SPY|2026-03-20|C|485|100"


@pytest.fixture
def sample_symbol() -> str:
    """Underlying symbol for config and order tests."""
    return "SPY"
