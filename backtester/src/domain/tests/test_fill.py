"""Fill domain object tests.

Reasoning: Fills represent execution reality. Broker produces Fills
from Orders via FillModel. Portfolio updates ONLY from fills. Every fill
must reference a valid order_id for audit trail and invariant checks.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.fill import Fill


def test_fill_create_minimal(sample_ts: datetime) -> None:
    """F1: Create Fill with order_id, ts, fill_price, fill_qty.

    Reasoning: These are the minimum fields required to update portfolio:
    which order was filled, when, at what price, and how many. Without them,
    position and cash updates are undefined.
    """
    fill = Fill(
        order_id="ord-001",
        ts=sample_ts,
        fill_price=485.25,
        fill_qty=1,
    )
    assert fill.order_id == "ord-001"
    assert fill.ts == sample_ts
    assert fill.fill_price == 485.25
    assert fill.fill_qty == 1


def test_fill_fees_and_liquidity_default(sample_ts: datetime) -> None:
    """F2: fees defaults to 0.0; liquidity_flag optional.

    Reasoning: FeeModel may add fees later; Fill must support them. liquidity_flag
    (maker/taker) is optional for MVP but the field must exist for extensibility.
    """
    fill = Fill(
        order_id="ord-002",
        ts=sample_ts,
        fill_price=485.50,
        fill_qty=2,
    )
    assert fill.fees == 0.0
    assert fill.liquidity_flag is None

    fill_with_fees = Fill(
        order_id="ord-003",
        ts=sample_ts,
        fill_price=485.50,
        fill_qty=1,
        fees=0.65,
        liquidity_flag="taker",
    )
    assert fill_with_fees.fees == 0.65
    assert fill_with_fees.liquidity_flag == "taker"


def test_fill_positive_qty_and_price(sample_ts: datetime) -> None:
    """F3: fill_qty is positive; fill_price is positive.

    Reasoning: FillModel produces fills with positive qty (actual execution size).
    Side comes from the Order. Negative fill_qty would break position math.
    Fill price must be positive for P&L calculation.
    """
    fill = Fill(
        order_id="ord-004",
        ts=sample_ts,
        fill_price=485.0,
        fill_qty=1,
    )
    assert fill.fill_qty > 0
    assert fill.fill_price > 0


def test_fill_order_id_stable_string(sample_ts: datetime) -> None:
    """F4: Fill references valid order_id (string).

    Reasoning: Every fill references a valid order id. Stable string
    IDs enable lookup in order log and invariant assertion (no orphan fills).
    """
    fill = Fill(
        order_id="ord-abc-123",
        ts=sample_ts,
        fill_price=485.25,
        fill_qty=1,
    )
    assert isinstance(fill.order_id, str)
    assert len(fill.order_id) > 0
