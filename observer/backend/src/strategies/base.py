"""BaseStrategy ABC and Requirements — the strategy contract.

All user strategies inherit from BaseStrategy. The engine calls
requirements() to pre-check data, then evaluate() on bar close.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from core.candidate import TradeCandidate
from state.context import Context


@dataclass(frozen=True)
class Requirements:
    """Declares what data a strategy needs from the market state.

    Reasoning: The engine uses this to verify the strategy has sufficient data
    before calling evaluate(). Prevents strategies from failing on missing data.
    """

    symbols: list[str]
    timeframes: list[str]
    lookback: int
    needs_quotes: bool = False


class BaseStrategy(ABC):
    """Base class for all user strategies.

    Reasoning: Strategies are pure logic — they read from Context and emit
    TradeCandidate[]. No direct API calls. No state mutation.
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def requirements(self) -> Requirements: ...

    @abstractmethod
    def evaluate(self, ctx: Context) -> list[TradeCandidate]: ...
