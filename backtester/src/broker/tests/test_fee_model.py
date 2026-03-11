"""Tests for FeeModel."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.broker.fee_model import FeeModelConfig, compute_fees
from src.domain.fill import Fill
from src.domain.order import Order


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


@pytest.fixture
def order() -> Order:
    return Order(
        id="ord-1",
        ts=_utc(2026, 1, 2, 14, 35),
        instrument_id="SPY|2026-01-17|C|480|100",
        side="BUY",
        qty=5,
        order_type="market",
    )


@pytest.fixture
def fill() -> Fill:
    return Fill(order_id="ord-1", ts=_utc(2026, 1, 2, 14, 35), fill_price=5.30, fill_qty=5, fees=0.0)


def test_compute_fees_per_contract_and_per_order(order: Order, fill: Fill) -> None:
    """Per-contract fee + per-order fee."""
    config = FeeModelConfig(per_contract=0.65, per_order=0.50)
    fees = compute_fees(order, fill, config)
    assert fees == pytest.approx(0.65 * 5 + 0.50)


def test_compute_fees_zero_config(order: Order, fill: Fill) -> None:
    """Zero config returns 0."""
    config = FeeModelConfig(per_contract=0.0, per_order=0.0)
    assert compute_fees(order, fill, config) == 0.0


def test_compute_fees_per_order_only(order: Order, fill: Fill) -> None:
    """Per-order fee only."""
    config = FeeModelConfig(per_contract=0.0, per_order=1.00)
    assert compute_fees(order, fill, config) == pytest.approx(1.0)


def test_compute_fees_per_contract_only(order: Order, fill: Fill) -> None:
    """Per-contract fee only."""
    config = FeeModelConfig(per_contract=0.50, per_order=0.0)
    assert compute_fees(order, fill, config) == pytest.approx(0.50 * 5)
