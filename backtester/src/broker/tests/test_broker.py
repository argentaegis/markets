"""Tests for Broker submit_orders."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.broker.broker import submit_orders, validate_order
from src.broker.fee_model import FeeModelConfig as FeeConfig
from src.broker.fill_model import FillModelConfig as FillConfig
from src.domain.fill import Fill
from src.domain.order import Order
from src.domain.portfolio import PortfolioState
from src.domain.quotes import Quote, Quotes
from src.domain.snapshot import MarketSnapshot


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


@pytest.fixture
def snapshot() -> MarketSnapshot:
    ts = _utc(2026, 1, 2, 14, 35)
    quotes = Quotes(
        ts=ts,
        quotes={"SPY|2026-01-17|C|480|100": Quote(bid=5.10, ask=5.30, mid=5.20)},
    )
    return MarketSnapshot(ts=ts, underlying_bar=None, option_quotes=quotes)


@pytest.fixture
def portfolio() -> PortfolioState:
    return PortfolioState(
        cash=100_000.0,
        positions={},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=100_000.0,
    )


@pytest.fixture
def fee_config() -> FeeConfig:
    return FeeConfig(per_contract=0.65, per_order=0.50)


@pytest.fixture
def fill_config() -> FillConfig:
    return FillConfig(synthetic_spread_bps=50.0)


def test_submit_orders_valid_order_produces_fill(
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
    fee_config: FeeConfig,
    fill_config: FillConfig,
) -> None:
    """Valid BUY order produces fill with fees."""
    order = Order(
        id="ord-1",
        ts=snapshot.ts,
        instrument_id="SPY|2026-01-17|C|480|100",
        side="BUY",
        qty=2,
        order_type="market",
    )
    fills = submit_orders(
        [order], snapshot, portfolio, symbol="SPY", fee_config=fee_config, fill_config=fill_config
    )
    assert len(fills) == 1
    assert fills[0].order_id == order.id
    assert fills[0].fill_price == 5.30
    assert fills[0].fill_qty == 2
    assert fills[0].fees == pytest.approx(0.65 * 2 + 0.50)


def test_submit_orders_rejected_order_no_fill(
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
    fee_config: FeeConfig,
    fill_config: FillConfig,
) -> None:
    """Rejected order (unknown instrument) produces no fill."""
    order = Order(
        id="ord-1",
        ts=snapshot.ts,
        instrument_id="SPY|2026-01-17|C|999|100",
        side="BUY",
        qty=1,
        order_type="market",
    )
    fills = submit_orders(
        [order], snapshot, portfolio, symbol="SPY", fee_config=fee_config, fill_config=fill_config
    )
    assert len(fills) == 0


def test_submit_orders_multiple_orders(
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
    fee_config: FeeConfig,
    fill_config: FillConfig,
) -> None:
    """Multiple orders: valid produce fills, invalid produce none."""
    orders = [
        Order(
            id="ord-1",
            ts=snapshot.ts,
            instrument_id="SPY|2026-01-17|C|480|100",
            side="BUY",
            qty=1,
            order_type="market",
        ),
        Order(
            id="ord-2",
            ts=snapshot.ts,
            instrument_id="SPY|2026-01-17|C|480|100",
            side="SELL",
            qty=1,
            order_type="market",
        ),
    ]
    fills = submit_orders(
        orders, snapshot, portfolio, symbol="SPY", fee_config=fee_config, fill_config=fill_config
    )
    assert len(fills) == 2
    assert fills[0].fill_price == 5.30
    assert fills[1].fill_price == 5.10
