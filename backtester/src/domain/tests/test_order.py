"""Order domain object tests.

Reasoning: Orders represent trading intent. Strategy produces Orders;
Broker/Execution produces Fills. Orders must be immutable so they cannot be
mutated after submission. All IDs must be stable strings for logging and audit.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.order import Order


def test_order_create_minimal(sample_ts: datetime, sample_contract_id: str) -> None:
    """O1: Create Order with id, ts, instrument_id, side, qty, order_type.

    Reasoning: These are the minimum required fields for the Broker to process
    an order. Without them, execution cannot proceed. Strategy emits Orders;
    we must be able to construct them from a snapshot.
    """
    order = Order(
        id="ord-001",
        ts=sample_ts,
        instrument_id=sample_contract_id,
        side="BUY",
        qty=1,
        order_type="market",
    )
    assert order.id == "ord-001"
    assert order.ts == sample_ts
    assert order.instrument_id == sample_contract_id
    assert order.side == "BUY"
    assert order.qty == 1
    assert order.order_type == "market"
    assert order.limit_price is None
    assert order.tif == "GTC"


def test_order_immutable(sample_ts: datetime, sample_contract_id: str) -> None:
    """O2: Order is immutable (frozen dataclass).

    Reasoning: Once submitted, an order must not be altered. Mutation could
    cause audit inconsistencies or race conditions in the simulation loop.
    """
    order = Order(
        id="ord-002",
        ts=sample_ts,
        instrument_id=sample_contract_id,
        side="SELL",
        qty=2,
        order_type="market",
    )
    with pytest.raises(AttributeError):
        order.qty = 3  # type: ignore[misc]


def test_order_limit_has_price(sample_ts: datetime, sample_contract_id: str) -> None:
    """O3: Order with limit order_type has limit_price; market has limit_price=None.

    Reasoning: FillModel needs limit_price for limit orders; market orders
    fill at best available. Mixing these would cause incorrect fill logic.
    """
    limit_order = Order(
        id="ord-003",
        ts=sample_ts,
        instrument_id=sample_contract_id,
        side="BUY",
        qty=1,
        order_type="limit",
        limit_price=485.50,
    )
    assert limit_order.order_type == "limit"
    assert limit_order.limit_price == 485.50

    market_order = Order(
        id="ord-004",
        ts=sample_ts,
        instrument_id=sample_contract_id,
        side="BUY",
        qty=1,
        order_type="market",
    )
    assert market_order.limit_price is None


def test_order_tif_defaults_to_gtc(sample_ts: datetime, sample_contract_id: str) -> None:
    """O4: tif defaults to "GTC".

    Reasoning: GTC (Good Till Cancelled) is the common default for backtest.
    IOC/FOK can be added later; MVP defaults avoid config surface.
    """
    order = Order(
        id="ord-005",
        ts=sample_ts,
        instrument_id=sample_contract_id,
        side="BUY",
        qty=1,
        order_type="market",
    )
    assert order.tif == "GTC"


def test_order_instrument_id_accepts_contract_and_symbol(sample_ts: datetime) -> None:
    """O6: instrument_id accepts contract_id format and symbol.

    Reasoning: Options use contract_id (SPY|2026-03-20|C|485|100); underlying
    uses symbol (SPY). Order must support both for multi-asset strategies.
    """
    opt_order = Order(
        id="ord-006",
        ts=sample_ts,
        instrument_id="SPY|2026-03-20|C|485|100",
        side="BUY",
        qty=1,
        order_type="market",
    )
    assert opt_order.instrument_id == "SPY|2026-03-20|C|485|100"

    eq_order = Order(
        id="ord-007",
        ts=sample_ts,
        instrument_id="SPY",
        side="BUY",
        qty=100,
        order_type="market",
    )
    assert eq_order.instrument_id == "SPY"
