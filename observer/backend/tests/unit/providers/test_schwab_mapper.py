"""Tests for Schwab symbol mapping and ContractSpec extraction."""

from __future__ import annotations

import pytest

from core.instrument import ContractSpec, FutureSymbol, InstrumentType
from core.market_data import DataQuality
from providers.schwab_mapper import (
    canonical_to_schwab,
    extract_contract_spec,
    map_security_status,
    schwab_to_canonical,
)


class TestSchwabToCanonical:
    def test_es_active_symbol(self):
        result = schwab_to_canonical("/ESH26")
        assert isinstance(result, FutureSymbol)
        assert result.root == "ES"
        assert result.contract_code == "H26"
        assert result.front_month_alias == "/ES"

    def test_nq_active_symbol(self):
        result = schwab_to_canonical("/NQM26")
        assert result.root == "NQ"
        assert result.contract_code == "M26"
        assert result.front_month_alias == "/NQ"

    def test_to_symbol_matches_canonical(self):
        result = schwab_to_canonical("/ESH26")
        assert result.to_symbol() == "ESH26"

    def test_root_only_symbol(self):
        result = schwab_to_canonical("/ES")
        assert result.root == "ES"
        assert result.contract_code == ""
        assert result.front_month_alias == "/ES"

    def test_unknown_format_raises(self):
        with pytest.raises(ValueError):
            schwab_to_canonical("INVALID")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            schwab_to_canonical("")


class TestCanonicalToSchwab:
    def test_es(self):
        assert canonical_to_schwab("ESH26") == "/ES"

    def test_nq(self):
        assert canonical_to_schwab("NQM26") == "/NQ"

    def test_cl(self):
        assert canonical_to_schwab("CLH26") == "/CL"

    def test_unknown_root_raises(self):
        with pytest.raises(ValueError):
            canonical_to_schwab("ZZZZZ")

    def test_two_char_root(self):
        assert canonical_to_schwab("ESH26") == "/ES"

    def test_roundtrip(self):
        fs = schwab_to_canonical("/ESH26")
        schwab_sym = canonical_to_schwab(fs.to_symbol())
        assert schwab_sym == "/ES"


class TestMapSecurityStatus:
    def test_normal(self):
        assert map_security_status("Normal") == DataQuality.OK

    def test_halted(self):
        assert map_security_status("Halted") == DataQuality.STALE

    def test_closed(self):
        assert map_security_status("Closed") == DataQuality.STALE

    def test_unknown(self):
        assert map_security_status("SomethingWeird") == DataQuality.PARTIAL

    def test_none(self):
        assert map_security_status(None) == DataQuality.PARTIAL


class TestExtractContractSpec:
    def test_full_fields(self):
        quote_data = {
            "quote": {
                "symbol": "/ESH26",
                "futureActiveSymbol": "/ESH26",
                "tick": 0.25,
                "futureMultiplier": 50.0,
            },
            "reference": {
                "futureTradingHours": "GLBX(de=1700-1600;0=1700-1600)",
            },
        }
        spec = extract_contract_spec(quote_data)
        assert isinstance(spec, ContractSpec)
        assert spec.symbol == "ESH26"
        assert spec.instrument_type == InstrumentType.FUTURE
        assert spec.tick_size == 0.25
        assert spec.point_value == 50.0
        assert spec.session is not None

    def test_nq_fields(self):
        quote_data = {
            "quote": {
                "futureActiveSymbol": "/NQM26",
                "tick": 0.25,
                "futureMultiplier": 20.0,
            },
            "reference": {},
        }
        spec = extract_contract_spec(quote_data)
        assert spec.symbol == "NQM26"
        assert spec.point_value == 20.0

    def test_missing_active_symbol_uses_symbol(self):
        quote_data = {
            "quote": {
                "symbol": "/ESH26",
                "tick": 0.25,
                "futureMultiplier": 50.0,
            },
            "reference": {},
        }
        spec = extract_contract_spec(quote_data)
        assert spec.symbol == "ESH26"

    def test_missing_tick_returns_none(self):
        quote_data = {
            "quote": {"futureMultiplier": 50.0},
            "reference": {},
        }
        assert extract_contract_spec(quote_data) is None

    def test_missing_multiplier_returns_none(self):
        quote_data = {
            "quote": {"tick": 0.25},
            "reference": {},
        }
        assert extract_contract_spec(quote_data) is None

    def test_fields_from_reference(self):
        quote_data = {
            "quote": {"futureActiveSymbol": "/ESH26"},
            "reference": {"tick": 0.25, "futureMultiplier": 50.0},
        }
        spec = extract_contract_spec(quote_data)
        assert spec is not None
        assert spec.tick_size == 0.25
