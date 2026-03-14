"""Phase 4.2: get_option_chain tests."""

from datetime import datetime, timezone

from src.loader.tests.conftest import make_provider, utc


def test_get_option_chain_filtered_subset() -> None:
    """Plan 266: Filtered chain is subset of full chain, within sigma band."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 5, 14, 30, 0))
    full = provider.get_option_chain("SPY", ts)
    # underlying 480, vol 0.2, sigma_limit 2 -> band ~25 for 6 DTE
    filtered = provider.get_option_chain_filtered("SPY", ts, underlying_price=480.0, sigma_limit=2.0, vol=0.20)
    assert set(filtered) <= set(full)
    assert len(filtered) <= len(full)
    # 480 strike should be in (ATM)
    assert "SPY|2026-01-17|C|480|100" in filtered or "SPY|2026-01-17|P|480|100" in filtered


def test_get_option_chain_filtered_tighter_sigma_excludes_far_strikes() -> None:
    """Plan 266: Tighter sigma_limit excludes strikes far from ATM."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 5, 14, 30, 0))
    loose = provider.get_option_chain_filtered("SPY", ts, underlying_price=480.0, sigma_limit=2.0, vol=0.20)
    tight = provider.get_option_chain_filtered("SPY", ts, underlying_price=480.0, sigma_limit=0.1, vol=0.20)
    assert len(tight) <= len(loose)
    assert set(tight) <= set(loose)


def test_returns_not_expired() -> None:
    """OC1: Returns contract_ids not expired at ts."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 5, 14, 30, 0))
    chain = provider.get_option_chain("SPY", ts)
    # expiry 2026-01-10, 2026-01-17, 2026-03-20 all > 2026-01-05
    # expiry 2026-01-10: on 2026-01-05, 2026-01-10 > 2026-01-05 so included
    assert len(chain) >= 3
    assert "SPY|2026-03-20|C|485|100" in chain


def test_sorted_deterministic() -> None:
    """OC2: Results sorted; same order on repeated calls."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 5, 14, 30, 0))
    c1 = provider.get_option_chain("SPY", ts)
    c2 = provider.get_option_chain("SPY", ts)
    assert c1 == c2
    assert c1 == sorted(c1)


def test_unknown_symbol() -> None:
    """OC3: Unknown symbol returns empty or per policy."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 5, 14, 30, 0))
    chain = provider.get_option_chain("QQQ", ts)
    assert chain == []


def test_uses_metadata_index() -> None:
    """OC4: Uses metadata index for filtering."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 5, 14, 30, 0))
    chain = provider.get_option_chain("SPY", ts)
    # All should be SPY contracts from metadata
    assert all(cid.startswith("SPY|") for cid in chain)
