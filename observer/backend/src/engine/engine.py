"""Engine — orchestrates strategy evaluation on bar-close events.

The engine owns state updates: on_bar() updates MarketState and triggers
evaluation when the bar's timeframe matches the configured eval_timeframe.
All methods are synchronous; the async boundary lives in the API layer (070).
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.candidate import TradeCandidate
from core.market_data import Bar
from core.portfolio import PortfolioState, create_mock_portfolio
from state.market_state import MarketState
from strategies.base import BaseStrategy

from .candidate_store import CandidateStore
from .config import EngineConfig


class Engine:
    """Orchestrates strategy evaluation on bar-close events.

    Reasoning: Strategies should not manage their own scheduling. The engine
    centralizes timing, runs strategies, and manages the candidate lifecycle.
    """

    def __init__(
        self,
        strategies: list[BaseStrategy],
        state: MarketState,
        config: EngineConfig,
        portfolio: PortfolioState | None = None,
    ) -> None:
        self._strategies = strategies
        self._state = state
        self._config = config
        self._portfolio = portfolio if portfolio is not None else create_mock_portfolio()
        self._store = CandidateStore()

    def on_bar(self, bar: Bar) -> list[TradeCandidate]:
        """Update MarketState with bar, then trigger evaluation if timeframe matches."""
        self._state.update_bar(bar)
        if bar.timeframe == self._config.eval_timeframe:
            return self.evaluate(timestamp=bar.timestamp)
        return []

    def evaluate(self, timestamp: datetime | None = None) -> list[TradeCandidate]:
        """Run all enabled strategies against current Context."""
        ts = timestamp if timestamp is not None else datetime.now(timezone.utc)
        ctx = self._state.get_context(timestamp=ts, portfolio=self._portfolio)

        all_new: list[TradeCandidate] = []
        for strategy in self._strategies:
            candidates = strategy.evaluate(ctx)
            if candidates:
                added = self._store.add(candidates)
                all_new.extend(added)

        self._store.invalidate_expired(now=ts)
        self._store.enforce_retention(self._config.max_candidates_per_strategy)
        return all_new

    def get_active_candidates(self, now: datetime | None = None) -> list[TradeCandidate]:
        """Return all non-expired candidates."""
        return self._store.get_active(now=now)

    def invalidate_expired(self, now: datetime | None = None) -> list[TradeCandidate]:
        """Remove and return candidates past their valid_until."""
        ts = now if now is not None else datetime.now(timezone.utc)
        return self._store.invalidate_expired(now=ts)
