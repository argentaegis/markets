"""Phase 1.4: contract_id parse/format tests."""

from datetime import date
import pytest

from src.domain.contract_id import format_contract_id, parse_contract_id, ParsedContractId


def test_format_contract_id() -> None:
    """CI1: format_contract_id produces canonical string."""
    s = format_contract_id("SPY", date(2026, 3, 20), "C", 450, 100)
    assert s == "SPY|2026-03-20|C|450|100"


def test_parse_contract_id() -> None:
    """CI2: parse_contract_id extracts underlying, expiry, right, strike."""
    parsed = parse_contract_id("SPY|2026-03-20|C|450|100")
    assert isinstance(parsed, ParsedContractId)
    assert parsed.underlying == "SPY"
    assert parsed.expiry == date(2026, 3, 20)
    assert parsed.right == "C"
    assert parsed.strike == 450.0
    assert parsed.multiplier == 100  # from format; metadata is authoritative


def test_roundtrip_parse_format() -> None:
    """CI3: Round-trip parse(format(...)) consistent."""
    underlying, expiry, right, strike, mult = "SPY", date(2026, 3, 20), "C", 450.5, 100
    s = format_contract_id(underlying, expiry, right, strike, mult)
    p = parse_contract_id(s)
    assert p.underlying == underlying
    assert p.expiry == expiry
    assert p.right == right
    assert p.strike == strike
    assert p.multiplier == mult


def test_parse_invalid_raises() -> None:
    """CI4: Invalid format raises ValueError."""
    with pytest.raises(ValueError, match="Invalid"):
        parse_contract_id("invalid")
    with pytest.raises(ValueError, match="Invalid"):
        parse_contract_id("SPY-2026-03-20-C-450-100")  # wrong separator


def test_parse_does_not_guess_multiplier() -> None:
    """CI5: Parser extracts multiplier from format; metadata is authoritative for P&L."""
    # Parser returns what's in the string; we don't infer multiplier elsewhere
    p = parse_contract_id("SPY|2026-03-20|C|450|10")
    assert p.multiplier == 10  # from format
    # Different product could have different multiplier in metadata
    p2 = parse_contract_id("SPY|2026-03-20|C|450|100")
    assert p2.multiplier == 100
