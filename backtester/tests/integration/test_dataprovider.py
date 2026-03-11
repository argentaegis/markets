"""Integration tests: DataProvider smoke (from validation.run)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.domain.contract import ContractSpec
from src.domain.quotes import Quote, QuoteStatus
from src.loader.provider import DataProviderConfig, LocalFileDataProvider


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def _resolve_data_paths() -> tuple[Path, Path]:
    """Resolve underlying and options paths from env or fixtures."""
    fixtures_root = Path(__file__).resolve().parents[2] / "src" / "loader" / "tests" / "fixtures"
    data_path = os.environ.get("VALIDATION_DATA_PATH")
    if data_path:
        data_root = Path(data_path).resolve()
        return data_root / "underlying", data_root / "options"
    return fixtures_root / "underlying", fixtures_root / "options"


@pytest.fixture
def dataprovider_config() -> DataProviderConfig:
    """DataProviderConfig; uses VALIDATION_DATA_PATH if set."""
    underlying_path, options_path = _resolve_data_paths()
    return DataProviderConfig(
        underlying_path=underlying_path,
        options_path=options_path,
        timeframes_supported=["1d", "1h", "1m"],
        missing_data_policy="RETURN_PARTIAL",
        max_quote_age=None,
    )


@pytest.fixture
def dataprovider(dataprovider_config: DataProviderConfig) -> LocalFileDataProvider:
    """LocalFileDataProvider for DataProvider integration tests."""
    return LocalFileDataProvider(dataprovider_config)


@pytest.mark.integration
def test_get_underlying_bars(dataprovider: LocalFileDataProvider) -> None:
    """Exercise get_underlying_bars; assert bars loaded."""
    start = _utc(2026, 1, 2, 21, 0)
    end = _utc(2026, 1, 8, 21, 0)
    bars = dataprovider.get_underlying_bars("SPY", "1d", start, end)
    assert bars.symbol == "SPY"
    assert bars.timeframe == "1d"
    assert len(bars.rows) >= 1
    for r in bars.rows:
        assert start <= r.ts <= end


@pytest.mark.integration
def test_get_option_chain(dataprovider: LocalFileDataProvider) -> None:
    """Exercise get_option_chain; assert chain loaded and sorted."""
    ts = _utc(2026, 1, 5, 14, 30)
    chain = dataprovider.get_option_chain("SPY", ts)
    assert isinstance(chain, list)
    assert len(chain) >= 1
    assert chain == sorted(chain)


@pytest.mark.integration
def test_get_option_quotes(dataprovider: LocalFileDataProvider) -> None:
    """Exercise get_option_quotes; assert quotes structure."""
    ts = _utc(2026, 1, 5, 14, 30)
    chain = dataprovider.get_option_chain("SPY", ts)
    contract_ids = chain[:3] if len(chain) >= 3 else chain
    quote_ts = _utc(2026, 1, 2, 14, 35)
    quotes = dataprovider.get_option_quotes(contract_ids, quote_ts)
    assert len(quotes.quotes) == len(contract_ids)
    for cid in contract_ids:
        val = quotes.quotes.get(cid)
        assert val is not None
        assert isinstance(val, (Quote, QuoteStatus)) or hasattr(val, "bid")


@pytest.mark.integration
def test_get_contract_metadata(dataprovider: LocalFileDataProvider) -> None:
    """Exercise get_contract_metadata for chain contracts."""
    ts = _utc(2026, 1, 5, 14, 30)
    chain = dataprovider.get_option_chain("SPY", ts)
    contract_ids = chain[:3] if len(chain) >= 3 else chain
    for cid in contract_ids:
        spec = dataprovider.get_contract_metadata(cid)
        assert spec is None or isinstance(spec, ContractSpec)


@pytest.mark.integration
def test_get_run_manifest_data(dataprovider: LocalFileDataProvider) -> None:
    """Exercise get_run_manifest_data; assert config and diagnostics structure."""
    manifest = dataprovider.get_run_manifest_data()
    assert "config" in manifest
    assert "diagnostics" in manifest
    diag = manifest["diagnostics"]
    assert "crossed_quotes_sanitized" in diag
