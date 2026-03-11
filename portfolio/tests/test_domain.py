"""Domain types: Position, PortfolioState, FillLike, OrderLike."""

from __future__ import annotations

import math

import pytest

from portfolio import FillLike, OrderLike, Position, PortfolioState


def test_position_create(sample_contract_id: str) -> None:
    """Create Position with all fields; defaults for multiplier and instrument_type."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=2,
        avg_price=4.85,
    )
    assert pos.instrument_id == sample_contract_id
    assert pos.qty == 2
    assert pos.avg_price == 4.85
    assert pos.multiplier == 1.0
    assert pos.instrument_type == "equity"


def test_position_create_with_option_params(sample_contract_id: str) -> None:
    """Position with explicit multiplier and instrument_type."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=2,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    assert pos.multiplier == 100.0
    assert pos.instrument_type == "option"


def test_position_short_qty(sample_contract_id: str) -> None:
    """qty can be negative (short position)."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=-1,
        avg_price=5.20,
        multiplier=100.0,
        instrument_type="option",
    )
    assert pos.qty == -1


def test_position_instrument_type(sample_contract_id: str, sample_symbol: str) -> None:
    """instrument_type: option, underlying, future."""
    opt_pos = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    assert opt_pos.instrument_type == "option"

    eq_pos = Position(
        instrument_id=sample_symbol,
        qty=100,
        avg_price=485.0,
        multiplier=1.0,
        instrument_type="equity",
    )
    assert eq_pos.instrument_type == "equity"


def test_portfolio_create_with_defaults() -> None:
    """PortfolioState with defaults for realized_pnl, unrealized_pnl, equity."""
    portfolio = PortfolioState(cash=100_000.0, positions={})
    assert portfolio.cash == 100_000.0
    assert portfolio.positions == {}
    assert portfolio.realized_pnl == 0.0
    assert portfolio.unrealized_pnl == 0.0
    assert portfolio.equity == 0.0


def test_portfolio_create_minimal(sample_contract_id: str) -> None:
    """PortfolioState with positions."""
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
    )
    assert portfolio.cash == 100_000.0
    assert len(portfolio.positions) == 1
    assert portfolio.positions[sample_contract_id].qty == 1


def test_portfolio_empty_positions() -> None:
    """positions can be empty dict."""
    portfolio = PortfolioState(cash=50_000.0, positions={})
    assert portfolio.positions == {}
    assert len(portfolio.positions) == 0


def test_portfolio_no_nan(sample_contract_id: str) -> None:
    """Portfolio with valid cash, equity, pnl — no NaN."""
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


def test_filllike_backtester_shape() -> None:
    """Objects with fill_price, fill_qty, fees satisfy FillLike."""
    class F:
        fill_price = 5.0
        fill_qty = 2
        fees = 1.0
    f = F()
    assert f.fill_price == 5.0
    assert f.fill_qty == 2
    assert f.fees == 1.0


def test_orderlike_backtester_shape() -> None:
    """Objects with instrument_id, side satisfy OrderLike."""
    class O:
        instrument_id = "SPY"
        side = "BUY"
    o = O()
    assert o.instrument_id == "SPY"
    assert o.side == "BUY"
