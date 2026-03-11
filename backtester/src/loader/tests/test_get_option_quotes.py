"""Phase 4.3: get_option_quotes tests."""

from datetime import datetime, timezone

import pytest

from src.domain.quotes import Quote, QuoteStatus, Quotes

from src.loader.tests.conftest import make_provider, utc


def test_asof_lookup() -> None:
    """OQ1: quote_at(ts) = last quote with quote_ts <= ts."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 2, 14, 33, 0))
    cid = "SPY|2026-01-17|C|480|100"
    q = provider.get_option_quotes([cid], ts)
    quote = q.quotes.get(cid)
    assert isinstance(quote, Quote)
    # at 14:33 raw bid=5.20 ask=5.10 (crossed); after Option B sanitize bid<=ask
    assert quote.bid <= quote.ask
    assert quote.crossed_market is True


def test_max_quote_age_strict_raises() -> None:
    """OQ2: Quote older than max_quote_age, RAISE policy raises."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 5, 14, 30, 0))
    cid = "SPY|2026-01-10|C|490|10"  # last quote 2025-12-01, very stale
    with pytest.raises(Exception, match="stale|MissingData"):
        provider.get_option_quotes([cid], ts)


def test_max_quote_age_non_strict_returns_stale() -> None:
    """OQ3: Non-strict returns STALE in Quotes.errors."""
    provider = make_provider(missing_data_policy="RETURN_PARTIAL")
    ts = utc(datetime(2026, 1, 5, 14, 30, 0))
    cid = "SPY|2026-01-10|C|490|10"
    q = provider.get_option_quotes([cid], ts)
    assert q.quotes.get(cid) == QuoteStatus.STALE
    assert any(e.reason == "STALE" for e in q.errors)


def test_all_keys_present() -> None:
    """OQ4: Quotes mapping has entry for every requested contract_id."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 2, 14, 35, 0))
    requested = ["SPY|2026-01-17|C|480|100", "SPY|2026-03-20|C|485|100", "nonexistent"]
    q = provider.get_option_quotes(requested, ts)
    assert len(q.quotes) == 3
    assert "SPY|2026-01-17|C|480|100" in q.quotes
    assert "SPY|2026-03-20|C|485|100" in q.quotes
    assert "nonexistent" in q.quotes


def test_missing_contract_has_reason() -> None:
    """OQ5: Missing contract: None or MISSING + reason in errors."""
    provider = make_provider(missing_data_policy="RETURN_PARTIAL")
    ts = utc(datetime(2026, 1, 2, 14, 35, 0))
    q = provider.get_option_quotes(["nonexistent_contract"], ts)
    assert q.quotes["nonexistent_contract"] == QuoteStatus.MISSING
    assert any(e.contract_id == "nonexistent_contract" for e in q.errors)


def test_crossed_market_sanitized() -> None:
    """OQ6: Crossed market sanitized and flagged."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 2, 14, 33, 0))
    cid = "SPY|2026-01-17|C|480|100"  # row has bid=5.20 ask=5.10
    q = provider.get_option_quotes([cid], ts)
    quote = q.quotes[cid]
    assert isinstance(quote, Quote)
    assert quote.bid <= quote.ask
    assert quote.crossed_market is True


def test_caching() -> None:
    """OQ7: Per-contract cache on first use."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 2, 14, 35, 0))
    cid = "SPY|2026-01-17|C|480|100"
    q1 = provider.get_option_quotes([cid], ts)
    q2 = provider.get_option_quotes([cid], ts)
    assert q1.quotes[cid] == q2.quotes[cid]


def test_return_type_quotes() -> None:
    """OQ8: Return type is Quotes."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 2, 14, 35, 0))
    q = provider.get_option_quotes(["SPY|2026-01-17|C|480|100"], ts)
    assert isinstance(q, Quotes)
