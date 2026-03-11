"""Integration tests: underlying fetch/validate (from validation.underlying)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from src.marketdata.symbols import resolve
from src.marketdata.underlying.export import filter_range
from src.marketdata.underlying.sources.registry import get_converter, get_provider
from src.marketdata.underlying.storage import read_cache, write_cache
from src.marketdata.underlying.validate import ValidationError, validate_canonical


@pytest.mark.network
@pytest.mark.integration
def test_underlying_fetch_and_validate() -> None:
    """Read cache or fetch SPY 1d 2026-01-01..2026-02-01; validate canonical format."""
    symbol = "SPY"
    interval = "1d"
    start = date(2026, 1, 1)
    end = date(2026, 2, 1)
    provider_name = "massive"
    provider_symbol = resolve(symbol, provider_name)

    df = read_cache(provider_name, symbol, interval, start, end)
    if df is None:
        df = read_cache("polygon", symbol, interval, start, end)
    if df is None:
        provider = get_provider(provider_name)
        converter = get_converter(provider_name)
        raw = provider.get_ohlcv_raw(provider_symbol, start, end, interval)
        df = converter.to_canonical(raw)
        if not df.empty:
            write_cache(
                df,
                provider=provider_name,
                user_symbol=symbol,
                provider_symbol=provider_symbol,
                interval=interval,
                start=start,
                end=end,
                source="Massive REST",
            )

    assert df is not None and not df.empty, f"No data for {symbol} {interval} {start}..{end}"
    filtered = filter_range(df, start, end)
    assert not filtered.empty, f"No bars in range {start}..{end}"
    validate_canonical(filtered)
