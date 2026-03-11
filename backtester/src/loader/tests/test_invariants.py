"""Phase 6.2: Invariant tests."""

import math
from datetime import datetime, timezone

from src.loader.tests.conftest import make_provider, utc


def test_no_nan_in_bars() -> None:
    """I1: No NaN in Bars for in-range bars."""
    provider = make_provider()
    start = utc(datetime(2026, 1, 2, 21, 0, 0))
    end = utc(datetime(2026, 1, 8, 21, 0, 0))
    bars = provider.get_underlying_bars("SPY", "1d", start, end)
    for r in bars.rows:
        assert not math.isnan(r.open)
        assert not math.isnan(r.high)
        assert not math.isnan(r.low)
        assert not math.isnan(r.close)
        assert not math.isnan(r.volume)


def test_data_range_in_run_manifest() -> None:
    """I3: Log data range (min/max ts) for run manifest — observable via get_run_manifest_data."""
    provider = make_provider()
    start = utc(datetime(2026, 1, 2, 21, 0, 0))
    end = utc(datetime(2026, 1, 8, 21, 0, 0))
    provider.get_underlying_bars("SPY", "1d", start, end)
    manifest = provider.get_run_manifest_data()
    assert "diagnostics" in manifest
    assert "data_ranges" in manifest["diagnostics"]
    assert "SPY|1d" in manifest["diagnostics"]["data_ranges"]
    dr = manifest["diagnostics"]["data_ranges"]["SPY|1d"]
    assert "min_ts" in dr
    assert "max_ts" in dr


def test_quote_missingness_in_run_manifest() -> None:
    """I4: Log missingness when RETURN_PARTIAL or quotes STALE — observable via get_run_manifest_data."""
    provider = make_provider(missing_data_policy="RETURN_PARTIAL")
    ts = utc(datetime(2026, 1, 5, 14, 30, 0))
    provider.get_option_quotes(["SPY|2026-01-10|C|490|10"], ts)  # stale quote
    manifest = provider.get_run_manifest_data()
    assert "diagnostics" in manifest
    assert "quote_missingness" in manifest["diagnostics"]
    missing = manifest["diagnostics"]["quote_missingness"]
    assert any(m.get("reason") == "STALE" for m in missing)
