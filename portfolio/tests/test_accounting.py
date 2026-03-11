"""Portfolio accounting tests. Port from backtester for parity verification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from portfolio import (
    Position,
    PortfolioState,
    apply_fill,
    assert_portfolio_invariants,
    mark_to_market,
    settle_positions,
)


@dataclass
class _Fill:
    fill_price: float
    fill_qty: int
    fees: float = 0.0


@dataclass
class _Order:
    instrument_id: str
    side: str


# --- apply_fill ---


def test_apply_fill_buy_opens_long_position(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Buy opens long position: cash decreases, position added."""
    portfolio = PortfolioState(cash=100_000.0, positions={})
    order = _Order(instrument_id=sample_contract_id, side="BUY")
    fill = _Fill(fill_price=4.85, fill_qty=2, fees=1.0)
    result = apply_fill(portfolio, fill, order, multiplier=100.0, instrument_type="option")
    assert result.cash == pytest.approx(99_029.0)
    assert sample_contract_id in result.positions
    pos = result.positions[sample_contract_id]
    assert pos.qty == 2
    assert pos.avg_price == 4.85
    assert pos.multiplier == 100.0
    assert pos.instrument_type == "option"
    assert result.realized_pnl == 0.0


def test_apply_fill_sell_closes_position(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Sell closes position; realized P&L on close."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=2,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=99_000.0,
        positions={sample_contract_id: pos},
        equity=99_000.0 + 2 * 4.85 * 100,
    )
    order = _Order(instrument_id=sample_contract_id, side="SELL")
    fill = _Fill(fill_price=5.20, fill_qty=2, fees=1.0)
    result = apply_fill(portfolio, fill, order, multiplier=100.0, instrument_type="option")
    assert result.cash == pytest.approx(100_039.0)
    assert sample_contract_id not in result.positions
    assert result.realized_pnl == pytest.approx(70.0)


def test_apply_fill_sell_partial_close(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Sell reduces position; partial close; realized P&L on closed portion."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=3,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=98_500.0,
        positions={sample_contract_id: pos},
    )
    order = _Order(instrument_id=sample_contract_id, side="SELL")
    fill = _Fill(fill_price=5.20, fill_qty=1, fees=0.5)
    result = apply_fill(portfolio, fill, order, multiplier=100.0, instrument_type="option")
    assert result.cash == pytest.approx(99_019.5)
    assert result.positions[sample_contract_id].qty == 2
    assert result.positions[sample_contract_id].avg_price == 4.85
    assert result.realized_pnl == pytest.approx(35.0)


def test_apply_fill_sell_opens_short(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Sell to open creates short position (negative qty)."""
    portfolio = PortfolioState(cash=100_000.0, positions={})
    order = _Order(instrument_id=sample_contract_id, side="SELL")
    fill = _Fill(fill_price=5.20, fill_qty=1, fees=1.0)
    result = apply_fill(portfolio, fill, order, multiplier=100.0, instrument_type="option")
    assert result.cash == pytest.approx(100_000.0 + 5.20 * 100 - 1.0)
    assert result.positions[sample_contract_id].qty == -1
    assert result.positions[sample_contract_id].avg_price == 5.20


def test_apply_fill_add_to_existing_position(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Add to existing position: avg_price updates (weighted avg)."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=2,
        avg_price=4.80,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=99_040.0,
        positions={sample_contract_id: pos},
    )
    order = _Order(instrument_id=sample_contract_id, side="BUY")
    fill = _Fill(fill_price=5.00, fill_qty=1, fees=0.0)
    result = apply_fill(portfolio, fill, order, multiplier=100.0, instrument_type="option")
    assert result.positions[sample_contract_id].qty == 3
    assert result.positions[sample_contract_id].avg_price == pytest.approx(4.867, rel=0.01)


def test_apply_fill_multiplier_consistency(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Adding to existing position uses position's multiplier, not caller's."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=2,
        avg_price=4.80,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(cash=99_040.0, positions={sample_contract_id: pos})
    order = _Order(instrument_id=sample_contract_id, side="BUY")
    fill = _Fill(fill_price=5.00, fill_qty=1, fees=0.0)
    result = apply_fill(
        portfolio, fill, order,
        multiplier=999.0,
        instrument_type="wrong",
    )
    assert result.positions[sample_contract_id].multiplier == 100.0
    assert result.positions[sample_contract_id].instrument_type == "option"


def test_apply_fill_does_not_mutate_input(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """apply_fill returns new PortfolioState; does not mutate input."""
    portfolio = PortfolioState(cash=100_000.0, positions={})
    order = _Order(instrument_id=sample_contract_id, side="BUY")
    fill = _Fill(fill_price=4.85, fill_qty=1, fees=0.0)
    result = apply_fill(portfolio, fill, order)
    assert result is not portfolio
    assert portfolio.cash == 100_000.0
    assert len(portfolio.positions) == 0


# --- mark_to_market ---


def test_mark_to_market_updates_unrealized_and_equity(sample_contract_id: str) -> None:
    """mark_to_market computes per-position mark value; updates unrealized_pnl and equity."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=2,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    cash = 99_000.0
    portfolio = PortfolioState(
        cash=cash,
        positions={sample_contract_id: pos},
        equity=cash + 2 * 4.85 * 100,
    )
    marks = {sample_contract_id: 5.20}
    result = mark_to_market(portfolio, marks)
    total_mark_value = 2 * 5.20 * 100
    total_cost_basis = 2 * 4.85 * 100
    expected_unrealized = total_mark_value - total_cost_basis
    assert result.cash == cash
    assert result.positions == portfolio.positions
    assert result.realized_pnl == 0.0
    assert result.unrealized_pnl == pytest.approx(expected_unrealized)
    assert result.equity == pytest.approx(cash + total_mark_value)


def test_mark_to_market_short_position(sample_contract_id: str) -> None:
    """Short position: mark value negative; unrealized = mark_value - cost_basis."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=-1,
        avg_price=5.20,
        multiplier=100.0,
        instrument_type="option",
    )
    cash = 100_520.0
    portfolio = PortfolioState(
        cash=cash,
        positions={sample_contract_id: pos},
        equity=cash + (-1) * 5.20 * 100,
    )
    marks = {sample_contract_id: 4.85}
    result = mark_to_market(portfolio, marks)
    mark_value = -1 * 4.85 * 100
    cost_basis = -1 * 5.20 * 100
    expected_unrealized = mark_value - cost_basis
    assert result.unrealized_pnl == pytest.approx(expected_unrealized)
    assert result.equity == pytest.approx(cash + mark_value)


def test_mark_to_market_missing_mark_uses_cost_basis(sample_contract_id: str) -> None:
    """When mark missing, use cost basis (unrealized=0 for that position)."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    cash = 99_500.0
    portfolio = PortfolioState(cash=cash, positions={sample_contract_id: pos})
    marks: dict[str, float] = {}
    result = mark_to_market(portfolio, marks)
    assert result.unrealized_pnl == 0.0
    assert result.equity == pytest.approx(cash + 1 * 4.85 * 100)


def test_mark_to_market_realized_unchanged(sample_contract_id: str) -> None:
    """mark_to_market leaves realized_pnl unchanged."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=99_500.0,
        positions={sample_contract_id: pos},
        realized_pnl=150.0,
    )
    marks = {sample_contract_id: 5.50}
    result = mark_to_market(portfolio, marks)
    assert result.realized_pnl == 150.0


# --- assert_portfolio_invariants ---


def test_assert_invariants_passes_valid_portfolio(sample_contract_id: str) -> None:
    """Valid portfolio: equity == cash + sum(mark_value); no NaN; int qty."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    mark_value = 5.0 * 100.0
    cash = 99_500.0
    portfolio = PortfolioState(
        cash=cash,
        positions={sample_contract_id: pos},
        unrealized_pnl=15.0,
        equity=cash + mark_value,
    )
    marks = {sample_contract_id: 5.0}
    assert_portfolio_invariants(portfolio, marks=marks)


def test_assert_invariants_raises_on_equity_mismatch(sample_contract_id: str) -> None:
    """Raises when equity != cash + sum(mark_value)."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=99_500.0,
        positions={sample_contract_id: pos},
        equity=100_100.0,
    )
    marks = {sample_contract_id: 5.0}
    with pytest.raises(AssertionError, match="equity"):
        assert_portfolio_invariants(portfolio, marks=marks, tolerance=0.01)


def test_assert_invariants_raises_on_nan(sample_contract_id: str) -> None:
    """Raises when cash, equity, or pnl is NaN."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=float("nan"),
        positions={sample_contract_id: pos},
        equity=100_000.0,
    )
    marks = {sample_contract_id: 5.0}
    with pytest.raises(AssertionError, match="NaN"):
        assert_portfolio_invariants(portfolio, marks=marks)


def test_assert_invariants_raises_on_non_int_qty(sample_contract_id: str) -> None:
    """Raises when position qty is not integer."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    pos.qty = 1.5  # type: ignore[assignment]
    portfolio = PortfolioState(
        cash=99_500.0,
        positions={sample_contract_id: pos},
        equity=100_000.0,
    )
    marks = {sample_contract_id: 5.0}
    with pytest.raises(AssertionError, match="integer"):
        assert_portfolio_invariants(portfolio, marks=marks)


# --- settle_positions ---


def test_settle_positions_long_receives_cash(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Long position: close at settlement; long receives cash."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=2,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    cash = 99_000.0
    portfolio = PortfolioState(
        cash=cash,
        positions={sample_contract_id: pos},
    )
    settlements = {sample_contract_id: 2.50}
    result = settle_positions(portfolio, settlements)
    assert sample_contract_id not in result.positions
    assert result.realized_pnl == pytest.approx((2.50 - 4.85) * 2 * 100)
    assert result.cash == pytest.approx(cash + 2 * 2.50 * 100)


def test_settle_positions_short_pays_cash(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Short position: close at settlement; short pays cash."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=-1,
        avg_price=5.20,
        multiplier=100.0,
        instrument_type="option",
    )
    cash = 100_520.0
    portfolio = PortfolioState(
        cash=cash,
        positions={sample_contract_id: pos},
    )
    settlements = {sample_contract_id: 2.50}
    result = settle_positions(portfolio, settlements)
    assert sample_contract_id not in result.positions
    assert result.realized_pnl == pytest.approx((5.20 - 2.50) * 1 * 100)
    assert result.cash == pytest.approx(cash - 1 * 2.50 * 100)


def test_settle_positions_skips_missing(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Only settle instruments in settlements dict; others unchanged."""
    other_id = "SPY|2026-04-20|C|490|100"
    pos1 = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    pos2 = Position(
        instrument_id=other_id,
        qty=1,
        avg_price=3.00,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=99_000.0,
        positions={sample_contract_id: pos1, other_id: pos2},
    )
    settlements = {sample_contract_id: 2.0}
    result = settle_positions(portfolio, settlements)
    assert sample_contract_id not in result.positions
    assert other_id in result.positions
    assert result.positions[other_id].qty == 1
