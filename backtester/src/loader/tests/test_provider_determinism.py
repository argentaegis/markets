"""Phase 4.5: Determinism tests."""

from datetime import datetime, timezone

from src.loader.tests.conftest import make_provider, utc


def test_same_config_same_results() -> None:
    """D1: Same config + same requests → identical results."""
    p1 = make_provider()
    p2 = make_provider()
    start = utc(datetime(2026, 1, 2, 21, 0, 0))
    end = utc(datetime(2026, 1, 6, 21, 0, 0))
    ts = utc(datetime(2026, 1, 2, 14, 35, 0))
    b1 = p1.get_underlying_bars("SPY", "1d", start, end)
    b2 = p2.get_underlying_bars("SPY", "1d", start, end)
    assert len(b1.rows) == len(b2.rows)
    for r1, r2 in zip(b1.rows, b2.rows):
        assert r1.ts == r2.ts and r1.close == r2.close
    c1 = p1.get_option_chain("SPY", ts)
    c2 = p2.get_option_chain("SPY", ts)
    assert c1 == c2


def test_sorted_option_chain() -> None:
    """D2: Option chain sorted for determinism."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 5, 14, 30, 0))
    chain = provider.get_option_chain("SPY", ts)
    assert chain == sorted(chain)
