"""Tests for core instrument identity types.

Covers InstrumentType enum, FutureSymbol, ContractSpec, and TradingSession.
"""

from __future__ import annotations

from datetime import time

import pytest

from core.instrument import (
    ContractSpec,
    FutureSymbol,
    InstrumentType,
    TradingSession,
)


class TestInstrumentType:
    def test_has_future(self):
        assert InstrumentType.FUTURE.value == "FUTURE"

    def test_has_equity(self):
        assert InstrumentType.EQUITY.value == "EQUITY"

    def test_has_option(self):
        assert InstrumentType.OPTION.value == "OPTION"


class TestFutureSymbol:
    def test_creation(self):
        sym = FutureSymbol(root="ES", contract_code="H26", front_month_alias="ES1!")
        assert sym.root == "ES"
        assert sym.contract_code == "H26"
        assert sym.front_month_alias == "ES1!"

    def test_immutability(self):
        sym = FutureSymbol(root="ES", contract_code="H26", front_month_alias="ES1!")
        with pytest.raises(AttributeError):
            sym.root = "NQ"

    def test_to_symbol(self):
        sym = FutureSymbol(root="ES", contract_code="H26", front_month_alias="ES1!")
        assert sym.to_symbol() == "ESH26"

    def test_to_symbol_nq(self):
        sym = FutureSymbol(root="NQ", contract_code="M26", front_month_alias="NQ1!")
        assert sym.to_symbol() == "NQM26"


ES_RTH = TradingSession(
    name="ES_RTH",
    start_time=time(9, 30),
    end_time=time(16, 0),
    timezone="US/Eastern",
)


class TestTradingSession:
    def test_creation(self):
        assert ES_RTH.name == "ES_RTH"
        assert ES_RTH.start_time == time(9, 30)
        assert ES_RTH.end_time == time(16, 0)
        assert ES_RTH.timezone == "US/Eastern"

    def test_immutability(self):
        with pytest.raises(AttributeError):
            ES_RTH.name = "other"

    def test_contains_within_session(self):
        assert ES_RTH.contains(time(10, 0)) is True

    def test_contains_at_open(self):
        assert ES_RTH.contains(time(9, 30)) is True

    def test_contains_at_close(self):
        assert ES_RTH.contains(time(16, 0)) is False

    def test_contains_before_open(self):
        assert ES_RTH.contains(time(9, 0)) is False

    def test_contains_after_close(self):
        assert ES_RTH.contains(time(17, 0)) is False


class TestContractSpec:
    def test_creation(self):
        spec = ContractSpec(
            symbol="ESH26",
            instrument_type=InstrumentType.FUTURE,
            tick_size=0.25,
            point_value=50.0,
            session=ES_RTH,
        )
        assert spec.symbol == "ESH26"
        assert spec.instrument_type == InstrumentType.FUTURE
        assert spec.tick_size == 0.25
        assert spec.point_value == 50.0
        assert spec.session == ES_RTH

    def test_immutability(self):
        spec = ContractSpec(
            symbol="ESH26",
            instrument_type=InstrumentType.FUTURE,
            tick_size=0.25,
            point_value=50.0,
            session=ES_RTH,
        )
        with pytest.raises(AttributeError):
            spec.tick_size = 0.50

    def test_nq_spec(self):
        spec = ContractSpec(
            symbol="NQM26",
            instrument_type=InstrumentType.FUTURE,
            tick_size=0.25,
            point_value=20.0,
            session=ES_RTH,
        )
        assert spec.symbol == "NQM26"
        assert spec.point_value == 20.0
