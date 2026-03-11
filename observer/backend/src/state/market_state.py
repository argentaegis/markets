"""MarketState — central store for current market truth.

Updated by provider events. Strategies consume state through the read-only
Context view returned by get_context(). The REST API uses MarketSnapshot
from get_snapshot().
"""

from __future__ import annotations

import collections
from datetime import datetime, timezone

from core.instrument import ContractSpec
from core.market_data import Bar, Quote
from core.portfolio import PortfolioState
from state.context import Context, MarketSnapshot


class MarketState:
    """Current market truth.

    Reasoning: Central store prevents strategies from managing their own state.
    Rolling bar windows allow lookback without unbounded memory.
    """

    def __init__(
        self,
        max_window_size: int = 500,
        specs: dict[str, ContractSpec] | None = None,
    ) -> None:
        self._max_window_size = max_window_size
        self._specs: dict[str, ContractSpec] = specs or {}
        self._quotes: dict[str, Quote] = {}
        self._bars: dict[str, dict[str, collections.deque[Bar]]] = {}

    # -- Quote tracking -----------------------------------------------------

    def update_quote(self, quote: Quote) -> None:
        self._quotes[quote.symbol] = quote

    def get_latest_quote(self, symbol: str) -> Quote | None:
        return self._quotes.get(symbol)

    # -- Bar tracking -------------------------------------------------------

    def update_bar(self, bar: Bar) -> None:
        sym_bars = self._bars.setdefault(bar.symbol, {})
        tf_deque = sym_bars.get(bar.timeframe)
        if tf_deque is None:
            tf_deque = collections.deque(maxlen=self._max_window_size)
            sym_bars[bar.timeframe] = tf_deque
        tf_deque.append(bar)

    def get_bars(self, symbol: str, timeframe: str, count: int) -> list[Bar]:
        sym_bars = self._bars.get(symbol)
        if sym_bars is None:
            return []
        tf_deque = sym_bars.get(timeframe)
        if tf_deque is None:
            return []
        if count >= len(tf_deque):
            return list(tf_deque)
        return list(tf_deque)[-count:]

    # -- Context / Snapshot -------------------------------------------------

    def _copy_bars(self) -> dict[str, dict[str, list[Bar]]]:
        return {
            sym: {tf: list(deq) for tf, deq in tf_map.items()}
            for sym, tf_map in self._bars.items()
        }

    def get_context(
        self,
        timestamp: datetime | None = None,
        portfolio: PortfolioState | None = None,
    ) -> Context:
        ts = timestamp if timestamp is not None else datetime.now(timezone.utc)
        if portfolio is not None:
            return Context(
                timestamp=ts,
                quotes=dict(self._quotes),
                bars=self._copy_bars(),
                specs=dict(self._specs),
                portfolio=portfolio,
            )
        return Context(
            timestamp=ts,
            quotes=dict(self._quotes),
            bars=self._copy_bars(),
            specs=dict(self._specs),
        )

    def get_snapshot(self, timestamp: datetime | None = None) -> MarketSnapshot:
        ts = timestamp if timestamp is not None else datetime.now(timezone.utc)
        return MarketSnapshot(
            timestamp=ts,
            quotes=dict(self._quotes),
            bars=self._copy_bars(),
            specs=dict(self._specs),
        )
