"""Tests for order validation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.broker.broker import validate_order
from src.domain.order import Order
from src.domain.portfolio import PortfolioState
from src.domain.quotes import Quote
from src.domain.snapshot import MarketSnapshot


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def _make_order(
    instrument_id: str = "SPY|2026-01-17|C|480|100",
    qty: int = 1,
    side: str = "BUY",
) -> Order:
    return Order(
        id="ord-1",
        ts=_utc(2026, 1, 2, 14, 35),
        instrument_id=instrument_id,
        side=side,
        qty=qty,
        order_type="market",
    )


@pytest.fixture
def snapshot_with_option() -> MarketSnapshot:
    """Snapshot with one option contract and underlying bar."""
    ts = _utc(2026, 1, 2, 14, 35)
    from src.domain.bars import BarRow

    bar = BarRow(ts=ts, open=480.0, high=481.0, low=479.0, close=480.8, volume=1000.0)
    from src.domain.quotes import Quotes

    quotes = Quotes(
        ts=ts,
        quotes={
            "SPY|2026-01-17|C|480|100": Quote(bid=5.10, ask=5.30, mid=5.20),
        },
    )
    return MarketSnapshot(ts=ts, underlying_bar=bar, option_quotes=quotes)


@pytest.fixture
def portfolio_with_cash() -> PortfolioState:
    """Portfolio with 100k cash, no positions."""
    return PortfolioState(
        cash=100_000.0,
        positions={},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=100_000.0,
    )


def test_validate_order_rejects_unknown_instrument(
    snapshot_with_option: MarketSnapshot,
    portfolio_with_cash: PortfolioState,
) -> None:
    """Reject order for contract_id not in snapshot."""
    order = _make_order(instrument_id="SPY|2026-01-17|C|999|100")
    assert validate_order(order, snapshot_with_option, portfolio_with_cash, symbol="SPY") is False


def test_validate_order_rejects_negative_qty(
    snapshot_with_option: MarketSnapshot,
    portfolio_with_cash: PortfolioState,
) -> None:
    """Reject order with qty <= 0."""
    order = _make_order(qty=0)
    assert validate_order(order, snapshot_with_option, portfolio_with_cash, symbol="SPY") is False

    order = _make_order(qty=-1)
    assert validate_order(order, snapshot_with_option, portfolio_with_cash, symbol="SPY") is False


def test_validate_order_rejects_insufficient_buying_power(
    snapshot_with_option: MarketSnapshot,
) -> None:
    """Reject BUY when estimated cost exceeds cash."""
    order = _make_order(qty=100)
    portfolio = PortfolioState(
        cash=1_000.0,
        positions={},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=1_000.0,
    )
    assert validate_order(order, snapshot_with_option, portfolio, symbol="SPY") is False


def test_validate_order_accepts_valid_order(
    snapshot_with_option: MarketSnapshot,
    portfolio_with_cash: PortfolioState,
) -> None:
    """Accept valid BUY order."""
    order = _make_order()
    assert validate_order(order, snapshot_with_option, portfolio_with_cash, symbol="SPY") is True


def test_validate_order_accepts_sell_with_position(
    snapshot_with_option: MarketSnapshot,
) -> None:
    """Accept valid SELL when position exists with sufficient qty."""
    from src.domain.position import Position

    contract_id = "SPY|2026-01-17|C|480|100"
    pos = Position(
        instrument_id=contract_id,
        qty=2,
        avg_price=5.20,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=100_000.0,
        positions={contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=100_000.0 + 2 * 5.20 * 100,
    )
    order = _make_order(qty=2, side="SELL")
    assert validate_order(order, snapshot_with_option, portfolio, symbol="SPY") is True
