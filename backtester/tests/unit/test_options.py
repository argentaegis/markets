"""Unit tests for options chain and quotes — use fixtures only, no network.

Mocks and fixture-based provider; no Massive API, no fetch. All tests run offline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.loader.provider import DataProviderConfig, LocalFileDataProvider

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "src" / "loader" / "tests" / "fixtures"


def _fixture_provider() -> LocalFileDataProvider:
    """Provider configured with fixture paths only. No network."""
    config = DataProviderConfig(
        underlying_path=FIXTURES_ROOT / "underlying",
        options_path=FIXTURES_ROOT / "options",
        timeframes_supported=["1d", "1h", "1m"],
        missing_data_policy="RETURN_PARTIAL",
        max_quote_age=None,
    )
    return LocalFileDataProvider(config)


def test_options_chain_loads_from_fixtures() -> None:
    """Chain loads from fixture metadata; no network."""
    provider = _fixture_provider()
    ts = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)
    chain = provider.get_option_chain("SPY", ts)
    assert len(chain) >= 1
    assert all(cid.startswith("SPY|") for cid in chain)


def test_options_quotes_load_from_fixtures() -> None:
    """Quotes load from fixture CSVs; no network."""
    provider = _fixture_provider()
    ts = datetime(2026, 1, 2, 14, 33, tzinfo=timezone.utc)
    cid = "SPY|2026-01-17|C|480|100"
    quotes = provider.get_option_quotes([cid], ts)
    assert cid in quotes.quotes
    q = quotes.quotes[cid]
    assert hasattr(q, "bid") and hasattr(q, "ask")


def test_options_chain_unknown_symbol_empty() -> None:
    """Unknown symbol returns empty chain."""
    provider = _fixture_provider()
    ts = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)
    chain = provider.get_option_chain("QQQ", ts)
    assert chain == []
