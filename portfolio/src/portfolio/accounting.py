"""Accounting: apply_fill, mark_to_market, settle_positions, assert_portfolio_invariants."""

from __future__ import annotations

import math

from portfolio.domain import Position, PortfolioState
from portfolio.protocols import FillLike, OrderLike


def apply_fill(
    portfolio: PortfolioState,
    fill: FillLike,
    order: OrderLike,
    *,
    multiplier: float = 1.0,
    instrument_type: str = "equity",
) -> PortfolioState:
    """Apply a fill to portfolio. Updates cash, positions, realized_pnl.

    Reasoning: Order provides instrument_id and side; fill provides price/qty/fees.
    Returns new PortfolioState; never mutates input.
    When adding to existing position (same direction), uses position's multiplier
    and instrument_type for consistency.
    """
    instrument_id = order.instrument_id
    signed_qty = fill.fill_qty if order.side == "BUY" else -fill.fill_qty

    new_cash = portfolio.cash
    new_positions = dict(portfolio.positions)
    new_realized_pnl = portfolio.realized_pnl

    existing = new_positions.get(instrument_id)
    if existing is None:
        cost = fill.fill_price * fill.fill_qty * multiplier
        if order.side == "BUY":
            new_cash -= cost
        else:
            new_cash += cost
        new_cash -= fill.fees
        if signed_qty != 0:
            new_positions[instrument_id] = Position(
                instrument_id=instrument_id,
                qty=signed_qty,
                avg_price=fill.fill_price,
                multiplier=multiplier,
                instrument_type=instrument_type,
            )
    else:
        mult = existing.multiplier
        itype = existing.instrument_type
        cost = fill.fill_price * fill.fill_qty * mult
        if order.side == "BUY":
            new_cash -= cost
        else:
            new_cash += cost
        new_cash -= fill.fees

        new_qty = existing.qty + signed_qty
        if new_qty == 0:
            del new_positions[instrument_id]
            closed_qty = abs(signed_qty)
            if existing.qty > 0:
                new_realized_pnl += (fill.fill_price - existing.avg_price) * closed_qty * mult
            else:
                new_realized_pnl += (existing.avg_price - fill.fill_price) * closed_qty * mult
        elif (existing.qty > 0) == (signed_qty > 0):
            total_cost = existing.qty * existing.avg_price + signed_qty * fill.fill_price
            new_avg = total_cost / new_qty
            new_positions[instrument_id] = Position(
                instrument_id=instrument_id,
                qty=new_qty,
                avg_price=new_avg,
                multiplier=mult,
                instrument_type=itype,
            )
        else:
            close_qty = min(abs(existing.qty), abs(signed_qty))
            if existing.qty > 0:
                new_realized_pnl += (fill.fill_price - existing.avg_price) * close_qty * mult
            else:
                new_realized_pnl += (existing.avg_price - fill.fill_price) * close_qty * mult
            remaining = existing.qty + signed_qty
            if remaining == 0:
                del new_positions[instrument_id]
            else:
                new_positions[instrument_id] = Position(
                    instrument_id=instrument_id,
                    qty=remaining,
                    avg_price=existing.avg_price,
                    multiplier=mult,
                    instrument_type=itype,
                )

    total_position_value = sum(
        p.qty * p.avg_price * p.multiplier for p in new_positions.values()
    )
    new_equity = new_cash + total_position_value

    return PortfolioState(
        cash=new_cash,
        positions=new_positions,
        realized_pnl=new_realized_pnl,
        unrealized_pnl=0.0,
        equity=new_equity,
    )


def mark_to_market(
    portfolio: PortfolioState,
    marks: dict[str, float],
) -> PortfolioState:
    """Compute mark-to-market; update unrealized_pnl and equity.

    Reasoning: Per-position mark value = qty * mark * multiplier. When mark
    missing, use cost basis (unrealized=0 for that position). Positions unchanged.
    """
    total_mark_value = 0.0
    for instrument_id, pos in portfolio.positions.items():
        mark_price = marks.get(instrument_id)
        if mark_price is not None:
            total_mark_value += pos.qty * mark_price * pos.multiplier
        else:
            total_mark_value += pos.qty * pos.avg_price * pos.multiplier
    total_cost_basis = sum(
        pos.qty * pos.avg_price * pos.multiplier for pos in portfolio.positions.values()
    )
    new_unrealized = total_mark_value - total_cost_basis
    new_equity = portfolio.cash + total_mark_value
    return PortfolioState(
        cash=portfolio.cash,
        positions=portfolio.positions,
        realized_pnl=portfolio.realized_pnl,
        unrealized_pnl=new_unrealized,
        equity=new_equity,
    )


def settle_positions(
    portfolio: PortfolioState,
    settlements: dict[str, float],
) -> PortfolioState:
    """Settle positions at given prices. Closes each instrument; computes realized PnL.

    Reasoning: Generic settlement for options expiry, futures rolls, forced liquidation.
    settlements maps instrument_id -> settlement price.
    """
    new_positions = dict(portfolio.positions)
    new_cash = portfolio.cash
    new_realized = portfolio.realized_pnl

    for instrument_id, settlement_price in settlements.items():
        pos = new_positions.pop(instrument_id, None)
        if pos is None:
            continue
        settlement = pos.qty * settlement_price * pos.multiplier
        new_cash += settlement
        if pos.qty > 0:
            new_realized += (settlement_price - pos.avg_price) * pos.qty * pos.multiplier
        else:
            new_realized += (pos.avg_price - settlement_price) * abs(pos.qty) * pos.multiplier

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


def assert_portfolio_invariants(
    portfolio: PortfolioState,
    marks: dict[str, float] | None = None,
    tolerance: float = 0.01,
) -> None:
    """Raise if equity invariant violated, NaN present, or qty not int.

    Reasoning: When marks provided, verifies equity == cash + sum(mark_value).
    Always checks for NaN in cash/equity/pnl and int qty per position.
    """
    if math.isnan(portfolio.cash) or math.isnan(portfolio.equity):
        raise AssertionError("NaN in cash or equity")
    if math.isnan(portfolio.realized_pnl) or math.isnan(portfolio.unrealized_pnl):
        raise AssertionError("NaN in realized_pnl or unrealized_pnl")
    for pos in portfolio.positions.values():
        if not isinstance(pos.qty, int):
            raise AssertionError(
                f"Position {pos.instrument_id} qty must be integer, got {pos.qty}"
            )
    if marks is not None:
        total_mark_value = 0.0
        for instrument_id, pos in portfolio.positions.items():
            mark_price = marks.get(instrument_id)
            if mark_price is not None:
                total_mark_value += pos.qty * mark_price * pos.multiplier
            else:
                total_mark_value += pos.qty * pos.avg_price * pos.multiplier
        expected_equity = portfolio.cash + total_mark_value
        if abs(portfolio.equity - expected_equity) > tolerance:
            raise AssertionError(
                f"Equity invariant violated: equity={portfolio.equity} "
                f"!= cash + sum(mark_value)={expected_equity}"
            )
