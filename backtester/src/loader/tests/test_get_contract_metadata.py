"""Phase 4.4: get_contract_metadata tests."""

from datetime import date
import pytest

from src.loader.provider import MissingContractMetadata
from src.domain.contract import ContractSpec

from src.loader.tests.conftest import make_provider


def test_index_first_returns_full_record() -> None:
    """CM1: contract_id in metadata index → return full record including multiplier."""
    provider = make_provider()
    c = provider.get_contract_metadata("SPY|2026-03-20|C|485|100")
    assert c is not None
    assert c.contract_id == "SPY|2026-03-20|C|485|100"
    assert c.underlying_symbol == "SPY"
    assert c.strike == 485.0
    assert c.expiry == date(2026, 3, 20)
    assert c.right == "C"
    assert c.multiplier == 100.0


def test_not_in_index_raise() -> None:
    """CM2, CM4: Not in index, RAISE policy → MissingContractMetadata."""
    provider = make_provider()
    with pytest.raises(MissingContractMetadata, match="SPY\\|9999-01-01\\|C\\|999\\|100"):
        provider.get_contract_metadata("SPY|9999-01-01|C|999|100")


def test_return_partial_metadata_missing() -> None:
    """CM2: Not in index, RETURN_PARTIAL → metadata_missing=True, multiplier from config."""
    provider = make_provider(missing_data_policy="RETURN_PARTIAL")
    c = provider.get_contract_metadata("SPY|2026-06-19|C|500|100")
    assert c is not None
    assert c.underlying_symbol == "SPY"
    assert c.expiry == date(2026, 6, 19)
    assert c.multiplier == 100.0  # default_multiplier, not from format
    assert c.metadata_missing is True


def test_return_empty() -> None:
    """CM2: Not in index, RETURN_EMPTY → None."""
    provider = make_provider(missing_data_policy="RETURN_EMPTY")
    c = provider.get_contract_metadata("SPY|9999-01-01|C|999|100")
    assert c is None


def test_multiplier_from_index_not_format() -> None:
    """CM3: Multiplier from index; SPY|2026-01-10|C|490|10 has multiplier 10 in index."""
    provider = make_provider()
    c = provider.get_contract_metadata("SPY|2026-01-10|C|490|10")
    assert c is not None
    assert c.multiplier == 10.0  # from index, not 100 from format
