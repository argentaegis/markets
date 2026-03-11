"""Shared fixtures for state module unit tests."""

from __future__ import annotations

from datetime import datetime, time, timezone

import pytest

from core.instrument import ContractSpec, InstrumentType, TradingSession
from core.market_data import Bar, DataQuality, Quote

T0 = datetime(2026, 2, 24, 14, 30, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 2, 24, 14, 35, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 2, 24, 14, 40, 0, tzinfo=timezone.utc)

ES_SPEC = ContractSpec(
    symbol="ESH26",
    instrument_type=InstrumentType.FUTURE,
    tick_size=0.25,
    point_value=50.0,
    session=TradingSession(
        name="RTH",
        start_time=time(9, 30),
        end_time=time(16, 0),
        timezone="America/New_York",
    ),
)


@pytest.fixture()
def es_quote() -> Quote:
    return Quote(
        symbol="ESH26",
        bid=5400.25,
        ask=5400.50,
        last=5400.25,
        bid_size=120,
        ask_size=85,
        volume=1_200_000,
        timestamp=T0,
        source="sim",
        quality=DataQuality.OK,
    )


@pytest.fixture()
def nq_quote() -> Quote:
    return Quote(
        symbol="NQH26",
        bid=19500.00,
        ask=19500.50,
        last=19500.25,
        bid_size=50,
        ask_size=40,
        volume=500_000,
        timestamp=T0,
        source="sim",
        quality=DataQuality.OK,
    )


@pytest.fixture()
def es_bar() -> Bar:
    return Bar(
        symbol="ESH26",
        timeframe="5m",
        open=5400.00,
        high=5405.25,
        low=5398.50,
        close=5403.75,
        volume=45_000,
        timestamp=T0,
        source="sim",
        quality=DataQuality.OK,
    )
