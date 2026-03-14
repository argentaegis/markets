"""Tests for Broker submit_orders."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.broker.broker import submit_orders, validate_order
from src.broker.fee_schedules import get_broker_schedule
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


def _get_instrument_type_option_run(order: Order) -> str:
    """For tests: option contract IDs have | in them."""
    return "option" if "|" in order.instrument_id else "equity"


@pytest.fixture
def fill_config() -> FillConfig:
    return FillConfig(synthetic_spread_bps=50.0)


def test_submit_orders_valid_order_produces_fill(
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
    fill_config: FillConfig,
) -> None:
    """Valid BUY order produces fill with fees (tdameritrade schedule)."""
    order = Order(
        id="ord-1",
        ts=snapshot.ts,
        instrument_id="SPY|2026-01-17|C|480|100",
        side="BUY",
        qty=2,
        order_type="market",
    )
    fee_schedule = get_broker_schedule("tdameritrade")
    fills = submit_orders(
        [order], snapshot, portfolio, symbol="SPY",
        fee_schedule=fee_schedule,
        get_instrument_type=_get_instrument_type_option_run,
        fill_config=fill_config,
    )
    assert len(fills) == 1
    assert fills[0].order_id == order.id
    assert fills[0].fill_price == 5.30
    assert fills[0].fill_qty == 2
    assert fills[0].fees == pytest.approx(0.65 * 2 + 0.50)


def test_submit_orders_rejected_order_no_fill(
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
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
    fee_schedule = get_broker_schedule("zero")
    fills = submit_orders(
        [order], snapshot, portfolio, symbol="SPY",
        fee_schedule=fee_schedule,
        get_instrument_type=_get_instrument_type_option_run,
        fill_config=fill_config,
    )
    assert len(fills) == 0


def test_submit_orders_multiple_orders(
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
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
    fee_schedule = get_broker_schedule("tdameritrade")
    fills = submit_orders(
        orders, snapshot, portfolio, symbol="SPY",
        fee_schedule=fee_schedule,
        get_instrument_type=_get_instrument_type_option_run,
        fill_config=fill_config,
    )
    assert len(fills) == 2
    assert fills[0].fill_price == 5.30
    assert fills[1].fill_price == 5.10
