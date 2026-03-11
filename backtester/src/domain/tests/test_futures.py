"""Tests for FuturesContractSpec and TradingSession."""

from datetime import time

import pytest

from src.domain.futures import FuturesContractSpec, TradingSession


def test_trading_session_create() -> None:
    session = TradingSession(
        name="RTH",
        start_time=time(9, 30),
        end_time=time(16, 0),
        timezone="America/New_York",
    )
    assert session.name == "RTH"
    assert session.start_time == time(9, 30)
    assert session.end_time == time(16, 0)
    assert session.timezone == "America/New_York"


def test_futures_contract_spec_create() -> None:
    session = TradingSession("RTH", time(9, 30), time(16, 0), "America/New_York")
    spec = FuturesContractSpec(
        symbol="ESH26",
        tick_size=0.25,
        point_value=50.0,
        session=session,
    )
    assert spec.symbol == "ESH26"
    assert spec.tick_size == 0.25
    assert spec.point_value == 50.0
    assert spec.session.timezone == "America/New_York"


def test_futures_contract_spec_nq() -> None:
    session = TradingSession("RTH", time(9, 30), time(16, 0), "America/New_York")
    spec = FuturesContractSpec(
        symbol="NQH26",
        tick_size=0.25,
        point_value=20.0,
        session=session,
    )
    assert spec.point_value == 20.0


def test_futures_contract_spec_immutable() -> None:
    session = TradingSession("RTH", time(9, 30), time(16, 0), "America/New_York")
    spec = FuturesContractSpec("ESH26", 0.25, 50.0, session)
    with pytest.raises(Exception):
        spec.tick_size = 0.5
