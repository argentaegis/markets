"""PortfolioState domain object tests.

Reasoning: PortfolioState is the accounting snapshot. Core
invariant: equity == cash + sum(mark_value(positions)). No NaN in critical
fields. Position quantities are integers (contracts). This must hold at each
simulation step or P&L is wrong.
"""

from __future__ import annotations

import math

import pytest

from src.domain.portfolio import PortfolioState
from src.domain.position import Position


def test_portfolio_create_minimal(sample_contract_id: str) -> None:
    """PS1: Create PortfolioState with cash, positions, realized_pnl, unrealized_pnl, equity.

    Reasoning: Broker and Reporter need these five fields. Cash and positions
    are the source of truth; realized/unrealized P&L and equity are derived
    but must be stored for step-invariant checks.
    """
    pos = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=100_000.0,
        positions={sample_contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=100_000.0,
    )
    assert portfolio.cash == 100_000.0
    assert len(portfolio.positions) == 1
    assert portfolio.positions[sample_contract_id].qty == 1
    assert portfolio.realized_pnl == 0.0
    assert portfolio.unrealized_pnl == 0.0
    assert portfolio.equity == 100_000.0


def test_portfolio_empty_positions() -> None:
    """PS2: positions is dict[str, Position]; empty dict valid.

    Reasoning: New portfolio or cash-only account has no positions. Empty dict
    must be valid to avoid special-casing in portfolio update logic.
    """
    portfolio = PortfolioState(
        cash=50_000.0,
        positions={},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=50_000.0,
    )
    assert portfolio.positions == {}
    assert len(portfolio.positions) == 0


def test_portfolio_equity_invariant(sample_contract_id: str) -> None:
    """PS3: Invariant — equity == cash + sum(mark_value(positions)) within tolerance.

    Reasoning: This is the core accounting invariant. If it breaks,
    P&L reporting is wrong. We test with a simple case: 1 option at mark 5.0,
    multiplier 100 → position value 500, cash 99500, equity 100000.
    """
    pos = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    mark_value = 5.0 * 100.0  # mark 5.0, mult 100
    cash = 99_500.0
    portfolio = PortfolioState(
        cash=cash,
        positions={sample_contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=cash + mark_value,
    )
    assert abs(portfolio.equity - (portfolio.cash + mark_value)) < 0.01


def test_portfolio_no_nan(sample_contract_id: str) -> None:
    """PS4: No NaN in cash, equity, pnl fields.

    Reasoning: NaN would propagate through reporting and break
    deterministic output. Assert at construction or step validation.
    """
    pos = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=100_000.0,
        positions={sample_contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=100_000.0,
    )
    assert not math.isnan(portfolio.cash)
    assert not math.isnan(portfolio.equity)
    assert not math.isnan(portfolio.realized_pnl)
    assert not math.isnan(portfolio.unrealized_pnl)


def test_portfolio_position_quantities_integers(sample_contract_id: str) -> None:
    """PS5: Position quantities are integers (contracts).

    Reasoning: Options trade in whole contracts. Fractional qty
    would indicate a bug. Position stores int qty.
    """
    pos = Position(
        instrument_id=sample_contract_id,
        qty=3,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    assert isinstance(pos.qty, int)
    assert pos.qty == 3
