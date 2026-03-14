"""Tests for Strategy ABC."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from strategizer.base import Strategy
from strategizer.protocol import Requirements
from strategizer.types import BarInput, Signal


def test_strategy_cannot_be_instantiated() -> None:
    """Strategy is abstract; direct instantiation raises TypeError."""
    with pytest.raises(TypeError):
        Strategy()


class MinimalStrategy(Strategy):
    """Minimal concrete Strategy for testing. Returns [] from evaluate."""

    @property
    def name(self) -> str:
        return "minimal"

    def requirements(self) -> Requirements:
        return Requirements(symbols=["ESH26"], timeframes=["1m"], lookback=1)

    def evaluate(
        self,
        ts: datetime,
        bars_by_symbol: dict[str, dict[str, list[BarInput]]],
        specs: dict[str, object],
        portfolio: object,
        *,
        step_index: int | None = None,
        strategy_params: dict | None = None,
        option_chain: list[str] | None = None,
    ) -> list[Signal]:
        return []


def test_minimal_strategy_instantiable() -> None:
    strategy = MinimalStrategy()
    assert strategy.name == "minimal"


def test_minimal_strategy_requirements() -> None:
    strategy = MinimalStrategy()
    req = strategy.requirements()
    assert req.symbols == ["ESH26"]
    assert req.timeframes == ["1m"]
    assert req.lookback == 1


def test_minimal_strategy_evaluate_returns_empty() -> None:
    strategy = MinimalStrategy()
    ts = datetime(2026, 1, 15, 14, 35, 0, tzinfo=timezone.utc)
    result = strategy.evaluate(
        ts=ts,
        bars_by_symbol={},
        specs={},
        portfolio=object(),
    )
    assert result == []


def test_minimal_strategy_option_fetch_spec_returns_none() -> None:
    """Default option_fetch_spec returns None (use config)."""
    strategy = MinimalStrategy()
    ts = datetime(2026, 1, 15, 14, 35, 0, tzinfo=timezone.utc)

    class MockPortfolio:
        def get_positions(self) -> dict:
            return {}

        def get_cash(self) -> float:
            return 100_000.0

        def get_equity(self) -> float:
            return 100_000.0

    spec = strategy.option_fetch_spec(ts, MockPortfolio(), 480.0, 1, {})
    assert spec is None
