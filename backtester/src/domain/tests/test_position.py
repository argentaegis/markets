"""Position domain object tests.

Reasoning: Position represents current holding. Portfolio updates
from fills; position qty can be long (positive) or short (negative). Options
quantities are integers (contracts). Multiplier applied once for P&L.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.domain.position import Position


def test_position_create(sample_contract_id: str) -> None:
    """P1: Create Position with instrument_id, qty, avg_price, multiplier, instrument_type.

    Reasoning: Portfolio needs to track each position for mark-to-market and
    P&L. All five fields are required: instrument identifies the contract,
    qty/avg_price for cost basis, multiplier for option contract size.
    """
    pos = Position(
        instrument_id=sample_contract_id,
        qty=2,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    assert pos.instrument_id == sample_contract_id
    assert pos.qty == 2
    assert pos.avg_price == 4.85
    assert pos.multiplier == 100.0
    assert pos.instrument_type == "option"


def test_position_short_qty(sample_contract_id: str) -> None:
    """P2: qty can be negative (short position).

    Reasoning: Selling to open creates short options. Position math must
    handle negative qty for correct mark-to-market and expiration settlement.
    """
    short_pos = Position(
        instrument_id=sample_contract_id,
        qty=-1,
        avg_price=5.20,
        multiplier=100.0,
        instrument_type="option",
    )
    assert short_pos.qty == -1


def test_position_zero_qty(sample_contract_id: str) -> None:
    """P3: qty == 0 is valid (closed position).

    Reasoning: After closing a position, we may keep a placeholder for
    realized P&L audit, or remove from dict. Allowing qty=0 keeps the
    type simple; caller can choose to omit from positions dict.
    """
    closed = Position(
        instrument_id=sample_contract_id,
        qty=0,
        avg_price=0.0,
        multiplier=100.0,
        instrument_type="option",
    )
    assert closed.qty == 0


def test_position_instrument_type(sample_contract_id: str, sample_symbol: str) -> None:
    """P4: instrument_type is "option" or "underlying".

    Reasoning: Multi-asset portfolio may hold both. Instrument type affects
    how we value (options use contract multiplier; equity uses shares).
    """
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
        instrument_type="underlying",
    )
    assert eq_pos.instrument_type == "underlying"


def test_position_multiplier_positive(sample_contract_id: str) -> None:
    """P5: multiplier is positive (e.g. 100 for standard options).

    Reasoning: Multipliers applied exactly once. Negative multiplier
    would invert P&L. Standard equity options use 100; minis may differ.
    """
    pos = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    assert pos.multiplier > 0
