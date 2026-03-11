"""Tests for BarInput, PositionView, Signal."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from strategizer.types import BarInput, PositionView, Signal


def test_bar_input_creation() -> None:
    ts = datetime(2026, 1, 15, 14, 35, 0, tzinfo=timezone.utc)
    bar = BarInput(ts=ts, open=5400.0, high=5405.0, low=5398.0, close=5402.0, volume=1000)
    assert bar.ts == ts
    assert bar.open == 5400.0
    assert bar.high == 5405.0
    assert bar.low == 5398.0
    assert bar.close == 5402.0
    assert bar.volume == 1000


def test_bar_input_immutable() -> None:
    ts = datetime(2026, 1, 15, 14, 35, 0, tzinfo=timezone.utc)
    bar = BarInput(ts=ts, open=5400.0, high=5405.0, low=5398.0, close=5402.0, volume=1000)
    with pytest.raises(FrozenInstanceError):
        bar.close = 5410.0


def test_position_view_creation() -> None:
    pos = PositionView(instrument_id="ESH26", qty=2, avg_price=5400.0)
    assert pos.instrument_id == "ESH26"
    assert pos.qty == 2
    assert pos.avg_price == 5400.0


def test_position_view_immutable() -> None:
    pos = PositionView(instrument_id="ESH26", qty=2, avg_price=5400.0)
    with pytest.raises(FrozenInstanceError):
        pos.qty = 3


def test_signal_required_fields() -> None:
    ts = datetime(2026, 1, 15, 14, 35, 0, tzinfo=timezone.utc)
    sig = Signal(
        symbol="ESH26",
        direction="LONG",
        entry_type="STOP",
        entry_price=5410.0,
        stop_price=5390.0,
        targets=[5420.0, 5430.0],
    )
    assert sig.symbol == "ESH26"
    assert sig.direction == "LONG"
    assert sig.entry_type == "STOP"
    assert sig.entry_price == 5410.0
    assert sig.stop_price == 5390.0
    assert sig.targets == [5420.0, 5430.0]


def test_signal_optional_fields_defaults() -> None:
    sig = Signal(
        symbol="ESH26",
        direction="SHORT",
        entry_type="MARKET",
        entry_price=5400.0,
        stop_price=5410.0,
        targets=[],
    )
    assert sig.score == 0.0
    assert sig.explain == []
    assert sig.valid_until is None


def test_signal_optional_fields_explicit() -> None:
    ts = datetime(2026, 1, 15, 16, 0, 0, tzinfo=timezone.utc)
    sig = Signal(
        symbol="ESH26",
        direction="LONG",
        entry_type="LIMIT",
        entry_price=5410.0,
        stop_price=5390.0,
        targets=[5420.0],
        score=75.0,
        explain=["ORB breakout"],
        valid_until=ts,
    )
    assert sig.score == 75.0
    assert sig.explain == ["ORB breakout"]
    assert sig.valid_until == ts


def test_signal_immutable() -> None:
    sig = Signal(
        symbol="ESH26",
        direction="LONG",
        entry_type="MARKET",
        entry_price=5400.0,
        stop_price=5390.0,
        targets=[5410.0],
    )
    with pytest.raises(FrozenInstanceError):
        sig.score = 80.0
