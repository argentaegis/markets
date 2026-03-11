"""Phase 2.1: DataProvider ABC tests."""

from datetime import datetime, timezone

from src.loader.provider import DataProvider, LocalFileDataProvider
from src.loader.tests.conftest import default_provider_config


def test_dataprovider_has_required_methods() -> None:
    """DataProvider defines get_underlying_bars, get_option_chain, get_option_quotes, get_contract_metadata, get_futures_contract_spec."""
    assert hasattr(DataProvider, "get_underlying_bars")
    assert hasattr(DataProvider, "get_option_chain")
    assert hasattr(DataProvider, "get_option_quotes")
    assert hasattr(DataProvider, "get_contract_metadata")
    assert hasattr(DataProvider, "get_futures_contract_spec")


def test_concrete_impl_instantiable() -> None:
    """Concrete implementation can be instantiated and called."""
    config = default_provider_config()
    provider = LocalFileDataProvider(config)
    ts = datetime(2026, 1, 5, tzinfo=timezone.utc)
    chain = provider.get_option_chain("SPY", ts)
    assert isinstance(chain, list)
