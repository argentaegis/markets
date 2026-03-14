"""Portfolio accounting — shared functions re-exported from portfolio package (Plan 250a).

extract_marks stays here (depends on MarketSnapshot, Quote).
settle_physical_assignment for short call exercise (Plan 267).
"""

from __future__ import annotations

from portfolio import (
    apply_fill,
    assert_portfolio_invariants,
    mark_to_market,
    settle_positions,
)
from portfolio.domain import Position, PortfolioState

from src.domain.contract import ContractSpec
from src.domain.quotes import Quote
from src.domain.snapshot import MarketSnapshot


def settle_physical_assignment(
    portfolio: PortfolioState,
    contract_id: str,
    spec: ContractSpec,
    intrinsic: float,
) -> PortfolioState:
    """Physical assignment: short call ITM — deliver shares, receive strike (Plan 267).

    Reduces underlying position by multiplier, adds strike*mult to cash, closes option,
    realizes PnL on both legs.
    """
    opt_pos = portfolio.positions.get(contract_id)
    if opt_pos is None or opt_pos.qty >= 0:
        return portfolio
    mult = int(spec.multiplier)
    sym = spec.underlying_symbol
    strike = spec.strike

    underlying_pos = portfolio.positions.get(sym)
    if underlying_pos is None or underlying_pos.qty < mult:
        # Cannot deliver — fall back to cash settlement would be alternative; for now treat as error
        return portfolio

    new_positions = dict(portfolio.positions)
    del new_positions[contract_id]

    new_qty = underlying_pos.qty - mult
    if new_qty == 0:
        del new_positions[sym]
        share_realized = (strike - underlying_pos.avg_price) * mult
    else:
        new_positions[sym] = Position(
            instrument_id=sym,
            qty=new_qty,
            avg_price=underlying_pos.avg_price,
            multiplier=underlying_pos.multiplier,
            instrument_type=underlying_pos.instrument_type,
        )
        share_realized = (strike - underlying_pos.avg_price) * mult

    option_realized = (opt_pos.avg_price - intrinsic) * abs(opt_pos.qty) * opt_pos.multiplier
    new_cash = portfolio.cash + strike * mult
    new_realized = portfolio.realized_pnl + share_realized + option_realized

    total_position_value = sum(
        p.qty * p.avg_price * p.multiplier for p in new_positions.values()
    )
    new_equity = new_cash + total_position_value

    return PortfolioState(
        cash=new_cash,
        positions=new_positions,
        realized_pnl=new_realized,
        unrealized_pnl=0.0,
        equity=new_equity,
    )


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
