"""Portfolio accounting — shared functions re-exported from portfolio package (Plan 250a).

extract_marks stays here (depends on MarketSnapshot, Quote).
"""

from __future__ import annotations

from portfolio import (
    apply_fill,
    assert_portfolio_invariants,
    mark_to_market,
    settle_positions,
)
from src.domain.quotes import Quote
from src.domain.snapshot import MarketSnapshot


def settle_expirations(
    portfolio,
    ts: object,
    expired: dict[str, float],
):
    """Backward-compat wrapper: settle_positions(portfolio, expired). ts unused."""
    return settle_positions(portfolio, expired)


def extract_marks(snapshot: MarketSnapshot, symbol: str) -> dict[str, float]:
    """Extract marks from MarketSnapshot.

    Reasoning: Options use Quote.mid or (bid+ask)/2; underlying uses bar.close.
    For multi-symbol equity (underlying_bars_by_symbol), emits mark per symbol (263).
    Skips missing/stale quotes. Handles None bars/quotes gracefully.
    """
    result: dict[str, float] = {}
    if snapshot.underlying_bars_by_symbol is not None:
        for sym, bar in snapshot.underlying_bars_by_symbol.items():
            if bar is not None:
                result[sym] = bar.close
    elif snapshot.underlying_bar is not None:
        result[symbol] = snapshot.underlying_bar.close
    if snapshot.option_quotes is not None:
        for contract_id, q in snapshot.option_quotes.quotes.items():
            if isinstance(q, Quote):
                mark = q.mid if q.mid is not None else (q.bid + q.ask) / 2
                result[contract_id] = mark
    return result
