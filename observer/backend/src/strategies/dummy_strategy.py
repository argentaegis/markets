"""DummyStrategy — trivial strategy for pipeline validation.

Always emits one sample TradeCandidate when ESH26 5m bar data is present.
Used to validate the engine loop (step 060) and end-to-end wiring.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from core.candidate import Direction, EntryType, TradeCandidate
from state.context import Context

from .base import BaseStrategy, Requirements


class DummyStrategy(BaseStrategy):
    """Always-on test strategy that emits a sample candidate.

    Reasoning: Provides a concrete BaseStrategy implementation for wiring
    the engine and testing the full pipeline without real market logic.
    """

    NAME = "dummy"

    def __init__(self, symbols: list[str] | None = None) -> None:
        self._symbols = symbols or ["ESH26"]

    @property
    def name(self) -> str:
        return self.NAME

    def requirements(self) -> Requirements:
        return Requirements(
            symbols=self._symbols,
            timeframes=["5m"],
            lookback=1,
            needs_quotes=False,
        )

    def evaluate(self, ctx: Context) -> list[TradeCandidate]:
        symbol = self._symbols[0]
        bars = ctx.bars.get(symbol, {}).get("5m", [])
        if not bars:
            return []

        last = bars[-1]
        entry = last.close

        return [
            TradeCandidate(
                id=str(uuid.uuid4()),
                symbol=symbol,
                strategy=self.name,
                direction=Direction.LONG,
                entry_type=EntryType.LIMIT,
                entry_price=entry,
                stop_price=entry - 2.0,
                targets=[entry + 2.0, entry + 4.0],
                score=50.0,
                explain=[
                    "Dummy strategy",
                    "Always generates a sample candidate",
                    "For testing only",
                ],
                valid_until=ctx.timestamp + timedelta(minutes=5),
                tags={"strategy": "dummy", "setup": "test"},
                created_at=ctx.timestamp,
            )
        ]
