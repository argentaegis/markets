"""Phase 7.1: Golden run tests."""

from datetime import datetime, timezone

from src.loader.tests.conftest import make_provider, utc


def test_golden_deterministic() -> None:
    """G1: Golden fixture run produces deterministic output."""
    provider = make_provider()
    start = utc(datetime(2026, 1, 2, 21, 0, 0))
    end = utc(datetime(2026, 1, 8, 21, 0, 0))
    ts = utc(datetime(2026, 1, 2, 14, 35, 0))
    bars1 = provider.get_underlying_bars("SPY", "1d", start, end)
    chain1 = provider.get_option_chain("SPY", ts)
    quotes1 = provider.get_option_quotes(["SPY|2026-01-17|C|480|100", "SPY|2026-03-20|C|485|100"], ts)
    # Second run
    provider2 = make_provider()
    bars2 = provider2.get_underlying_bars("SPY", "1d", start, end)
    chain2 = provider2.get_option_chain("SPY", ts)
    quotes2 = provider2.get_option_quotes(["SPY|2026-01-17|C|480|100", "SPY|2026-03-20|C|485|100"], ts)
    assert len(bars1.rows) == len(bars2.rows)
    assert chain1 == chain2
    assert len(quotes1.quotes) == len(quotes2.quotes)


def test_golden_output_capturable_for_diff() -> None:
    """G2: Golden output can be captured and diffed for regression detection."""
    provider = make_provider()
    start = utc(datetime(2026, 1, 2, 21, 0, 0))
    end = utc(datetime(2026, 1, 8, 21, 0, 0))
    ts = utc(datetime(2026, 1, 2, 14, 35, 0))
    bars = provider.get_underlying_bars("SPY", "1d", start, end)
    chain = provider.get_option_chain("SPY", ts)
    quotes = provider.get_option_quotes(["SPY|2026-01-17|C|480|100"], ts)
    # Capture as diffable structure
    captured = {
        "bar_count": len(bars.rows),
        "bar_closes": [r.close for r in bars.rows],
        "chain": chain,
        "quote_count": len(quotes.quotes),
    }
    # Deterministic and comparable
    assert captured["bar_count"] == 5
    assert len(captured["chain"]) >= 1
