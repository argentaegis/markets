"""Integration tests: options data loading and quote resolution.

Uses exported options data (data/exports/options/spy) as primary source.
Falls back to cache providers or fixtures; fails if no real data available.
For unit tests with fixtures only, see tests/unit/test_options.py.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.loader.provider import DataProviderConfig, LocalFileDataProvider
from src.marketdata.config import CACHE_ROOT


_PROJECT_ROOT = CACHE_ROOT.parent.parent
_EXPORTS_OPTIONS_SPY = _PROJECT_ROOT / "data" / "exports" / "options" / "spy"
_FIXTURES_OPTIONS = _PROJECT_ROOT / "src" / "loader" / "tests" / "fixtures" / "options"
_FIXTURES_UNDERLYING = _PROJECT_ROOT / "src" / "loader" / "tests" / "fixtures" / "underlying"

_TEST_AS_OF_DATE = date(2024, 6, 15)


def _has_options_data(options_path: Path) -> bool:
    meta = options_path / "metadata" / "index.csv"
    if not meta.exists():
        return False
    with open(meta) as f:
        lines = [l for l in f if l.strip() and not l.startswith("underlying")]
    return len(lines) > 0


def _resolve_options_path() -> Path:
    """Resolve options data path. Prefers exports, then cache, then fixtures."""
    for candidate in [
        _EXPORTS_OPTIONS_SPY,
        CACHE_ROOT / "massive" / "options" / "spy",
        CACHE_ROOT / "polygon" / "options" / "spy",
    ]:
        if _has_options_data(candidate):
            return candidate
    return _FIXTURES_OPTIONS


def _build_provider(options_path: Path) -> LocalFileDataProvider:
    config = DataProviderConfig(
        underlying_path=_FIXTURES_UNDERLYING,
        options_path=options_path,
        missing_data_policy="RETURN_PARTIAL",
        max_quote_age=None,
    )
    return LocalFileDataProvider(config)


@pytest.mark.integration
def test_options_chain() -> None:
    """Options chain loads from exported or cached data."""
    options_path = _resolve_options_path()
    if options_path == _FIXTURES_OPTIONS:
        pytest.fail(
            "No exported or cached options data found. "
            "Import options data to data/exports/options/spy/ (requires metadata/index.csv and quotes.parquet)."
        )
    provider = _build_provider(options_path)
    ts = datetime.combine(_TEST_AS_OF_DATE, datetime.min.time()).replace(tzinfo=timezone.utc)
    chain = provider.get_option_chain("SPY", ts)
    assert len(chain) >= 1, "No option contracts for SPY"


@pytest.mark.integration
def test_options_quotes_integration() -> None:
    """Options quotes resolve with valid bid/ask from exported or cached data."""
    options_path = _resolve_options_path()
    if options_path == _FIXTURES_OPTIONS:
        pytest.fail(
            "No exported or cached options data found. "
            "Import options data to data/exports/options/spy/ (requires metadata/index.csv and quotes.parquet)."
        )
    provider = _build_provider(options_path)
    ts = datetime.combine(_TEST_AS_OF_DATE, datetime.min.time()).replace(tzinfo=timezone.utc)
    chain = provider.get_option_chain("SPY", ts)
    assert len(chain) >= 1, "No option contracts for SPY"

    sample = chain[:3]
    quotes = provider.get_option_quotes(sample, ts)
    has_valid_quotes = any(hasattr(quotes.quotes.get(cid), "bid") for cid in sample)
    assert has_valid_quotes, (
        f"No valid quotes for {sample}. Check data coverage around {_TEST_AS_OF_DATE}."
    )
