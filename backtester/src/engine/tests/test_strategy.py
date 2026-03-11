"""Strategy ABC tests — Phase 1 of 070.

Reasoning: Strategy (M3) is the only new domain concept for the engine loop.
ABC enforces on_step; NullStrategy provides a baseline for engine tests.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.order import Order
from src.domain.portfolio import PortfolioState
from src.domain.snapshot import MarketSnapshot
from src.engine.strategy import NullStrategy, Strategy


def _empty_snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        ts=datetime(2026, 1, 2, 21, 0, tzinfo=timezone.utc),
        underlying_bar=None,
        option_quotes=None,
    )


def _empty_portfolio() -> PortfolioState:
    return PortfolioState(
        cash=100_000.0,
        positions={},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=100_000.0,
    )


def test_strategy_abc_cannot_instantiate() -> None:
    """Strategy ABC cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Strategy()  # type: ignore[abstract]


def test_strategy_subclass_with_on_step_instantiates() -> None:
    """Concrete subclass implementing on_step can be created."""

    class MyStrategy(Strategy):
        def on_step(
            self,
            snapshot: MarketSnapshot,
            state_view: PortfolioState,
            step_index: int = 1,
        ) -> list[Order]:
            return []

    s = MyStrategy()
    assert isinstance(s, Strategy)


def test_null_strategy_returns_empty_list() -> None:
    """NullStrategy.on_step always returns []."""
    s = NullStrategy()
    result = s.on_step(_empty_snapshot(), _empty_portfolio())
    assert result == []


def test_null_strategy_is_strategy_subclass() -> None:
    """NullStrategy is a proper Strategy subclass."""
    assert issubclass(NullStrategy, Strategy)
    assert isinstance(NullStrategy(), Strategy)


def test_on_step_return_type_is_list_of_order() -> None:
    """on_step returns list[Order] (empty for NullStrategy)."""
    s = NullStrategy()
    result = s.on_step(_empty_snapshot(), _empty_portfolio())
    assert isinstance(result, list)
