"""Shared fixtures for core type tests.

Provides sample instruments, sessions, quotes, and bars used across test modules.
"""

from __future__ import annotations

from datetime import datetime, time, timezone

import pytest

from core.instrument import (
    ContractSpec,
    FutureSymbol,
    InstrumentType,
    TradingSession,
)
from core.market_data import Bar, DataQuality, Quote

NOW_UTC = datetime(2026, 2, 24, 14, 35, 0, tzinfo=timezone.utc)


@pytest.fixture
def es_rth() -> TradingSession:
    return TradingSession(
        name="ES_RTH",
        start_time=time(9, 30),
        end_time=time(16, 0),
        timezone="US/Eastern",
    )


@pytest.fixture
def es_symbol() -> FutureSymbol:
    return FutureSymbol(root="ES", contract_code="H26", front_month_alias="ES1!")


@pytest.fixture
def es_spec(es_rth: TradingSession) -> ContractSpec:
    return ContractSpec(
        symbol="ESH26",
        instrument_type=InstrumentType.FUTURE,
        tick_size=0.25,
        point_value=50.0,
        session=es_rth,
    )


@pytest.fixture
def sample_quote() -> Quote:
    return Quote(
        symbol="ESH26",
        bid=5400.25,
        ask=5400.50,
        last=5400.25,
        bid_size=120,
        ask_size=85,
        volume=1_200_000,
        timestamp=NOW_UTC,
        source="sim",
        quality=DataQuality.OK,
    )


@pytest.fixture
def sample_bar() -> Bar:
    return Bar(
        symbol="ESH26",
        timeframe="5m",
        open=5400.00,
        high=5405.25,
        low=5398.50,
        close=5403.75,
        volume=45_000,
        timestamp=NOW_UTC,
        source="sim",
        quality=DataQuality.OK,
    )
