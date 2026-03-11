"""Phase 1.2: Quote, QuoteStatus, Quotes tests."""

from datetime import datetime, timezone

from src.domain.quotes import Quote, QuoteError, QuoteStatus, Quotes


def test_quote_create_optional_fields() -> None:
    """Q1: Quote with bid, ask; optional fields can be None."""
    q = Quote.from_raw(bid=5.10, ask=5.20)
    assert q.bid == 5.10
    assert q.ask == 5.20
    assert q.mid is not None
    assert q.bid_size is None
    assert q.ask_size is None


def test_quotes_mapping_has_all_keys() -> None:
    """Q2, Q3: Quotes includes entry for every requested contract_id."""
    ts = datetime(2026, 1, 2, 14, 32, 0, tzinfo=timezone.utc)
    mapping = {
        "c1": Quote.from_raw(5.10, 5.20),
        "c2": None,
        "c3": QuoteStatus.MISSING,
    }
    qs = Quotes(ts=ts, quotes=mapping)
    assert len(qs.quotes) == 3
    assert "c1" in qs.quotes
    assert "c2" in qs.quotes
    assert "c3" in qs.quotes


def test_quotes_missing_has_reason() -> None:
    """Q4: Missing contract has None or QuoteStatus.MISSING; errors list includes reason."""
    ts = datetime(2026, 1, 2, 14, 32, 0, tzinfo=timezone.utc)
    errors = [QuoteError("c2", "MISSING", "No quote <= ts")]
    qs = Quotes(ts=ts, quotes={"c2": QuoteStatus.MISSING}, errors=errors)
    assert qs.quotes["c2"] == QuoteStatus.MISSING
    assert any(e.contract_id == "c2" and e.reason == "MISSING" for e in qs.errors)


def test_quotes_stale_flagged() -> None:
    """Q5: Stale contract has QuoteStatus.STALE or reason in errors."""
    ts = datetime(2026, 1, 2, 14, 32, 0, tzinfo=timezone.utc)
    errors = [QuoteError("c1", "STALE", "Quote age 120s > max 60s")]
    qs = Quotes(ts=ts, quotes={"c1": QuoteStatus.STALE}, errors=errors)
    assert qs.quotes["c1"] == QuoteStatus.STALE


def test_crossed_market_sanitize() -> None:
    """Q6: bid > ask → sanitized so bid <= ask; crossed_market=True."""
    q = Quote.from_raw(bid=5.20, ask=5.10)
    assert q.bid <= q.ask
    assert q.crossed_market is True


def test_crossed_market_option_b_mid_preserved() -> None:
    """Q7: Option B — mid preserved; bid/ask adjusted around mid."""
    q = Quote.from_raw(bid=5.20, ask=5.10, mid=5.15)
    assert q.mid == 5.15
    assert q.bid <= q.ask
    assert q.crossed_market is True


def test_quote_bid_eq_ask_no_crossed_flag() -> None:
    """Q8: bid == ask — no crossed flag."""
    q = Quote.from_raw(bid=5.10, ask=5.10)
    assert q.crossed_market is False
