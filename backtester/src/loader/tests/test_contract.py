"""Phase 1.3: ContractSpec tests."""

from datetime import date
import pytest

from src.domain.contract import ContractSpec


def test_contract_spec_create() -> None:
    """C1: Create ContractSpec with all fields."""
    c = ContractSpec(
        contract_id="SPY|2026-03-20|C|450|100",
        underlying_symbol="SPY",
        strike=450.0,
        expiry=date(2026, 3, 20),
        right="C",
        multiplier=100.0,
    )
    assert c.contract_id == "SPY|2026-03-20|C|450|100"
    assert c.multiplier == 100.0


def test_contract_spec_immutable() -> None:
    """C2: ContractSpec is immutable."""
    c = ContractSpec(
        contract_id="x",
        underlying_symbol="SPY",
        strike=100.0,
        expiry=date(2026, 3, 20),
        right="C",
        multiplier=100.0,
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        c.strike = 200.0
