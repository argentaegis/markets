"""Phase 5.1: MarketSnapshot build contract tests."""

from datetime import datetime, timezone

from src.domain.bars import BarRow
from src.domain.quotes import Quotes
from src.domain.snapshot import MarketSnapshot, build_market_snapshot

from src.loader.tests.conftest import make_provider, utc


def test_build_without_dataframe() -> None:
    """MS1: MarketSnapshot can be built from Bars (one bar) + Quotes + ts."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 2, 14, 35, 0))  # 1m bar + quotes available
    bars = provider.get_underlying_bars("SPY", "1m", ts, ts)
    quotes = provider.get_option_quotes(["SPY|2026-01-17|C|480|100"], ts)
    bar = bars.rows[0] if bars.rows else None
    snap = build_market_snapshot(ts, bar, quotes)
    assert isinstance(snap, MarketSnapshot)
    assert snap.ts == ts
    assert snap.underlying_bar is not None
    assert snap.option_quotes is not None
    assert isinstance(snap.underlying_bar, BarRow)
    assert isinstance(snap.option_quotes, Quotes)


def test_dataprovider_output_sufficient() -> None:
    """MS2: DataProvider output types sufficient for MarketSnapshot."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 2, 14, 35, 0))  # 1m bar + quotes available
    bars = provider.get_underlying_bars("SPY", "1m", ts, ts)
    quotes = provider.get_option_quotes(["SPY|2026-01-17|C|480|100"], ts)
    bar = bars.rows[0] if bars.rows else None
    snap = build_market_snapshot(ts, bar, quotes)
    assert snap.underlying_bar is not None
    assert hasattr(snap.underlying_bar, "ts")
    assert hasattr(snap.underlying_bar, "close")
    assert snap.option_quotes.quotes is not None
