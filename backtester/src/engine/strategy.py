"""Strategy ABC — M3 interface for the engine loop.

Strategy has no side effects. Receives MarketSnapshot + PortfolioState,
returns list[Order]. Engine calls on_step at each bar-close timestamp.

Reasoning: A1 requires Strategy to produce Orders (intent) only. Broker
converts to Fills (reality). ABC enforces interface for swappable strategies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.order import Order
from src.domain.portfolio import PortfolioState
from src.domain.snapshot import MarketSnapshot


class Strategy(ABC):
    """Abstract strategy. Subclass and implement on_step.

    Reasoning: 000 M3 spec. Single method keeps interface minimal.
    Strategy sees full snapshot and portfolio state; emits orders only.
    """

    @abstractmethod
    def on_step(
        self,
        snapshot: MarketSnapshot,
        state_view: PortfolioState,
        step_index: int = 1,
    ) -> list[Order]:
        """Evaluate snapshot and portfolio; return orders to submit.

        Must be pure — no side effects, no mutation of state_view.
        step_index: 1-based engine step for stateless strategies.
        """
        ...


class NullStrategy(Strategy):
    """Strategy that never trades. Returns [] on every step.

    Reasoning: Baseline for engine tests. Verifies loop mechanics
    (snapshot building, marking, invariants) without order flow noise.
    """

    def on_step(
        self,
        snapshot: MarketSnapshot,
        state_view: PortfolioState,
        step_index: int = 1,
    ) -> list[Order]:
        return []
