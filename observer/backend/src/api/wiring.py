"""Background tasks: consume_quotes, consume_bars.

These coroutines bridge async provider streams to the synchronous engine
and broadcast updates to connected WebSocket clients. Optional StateStore
persistence is handled here (not in MarketState) to keep the in-memory
hot path clean.
"""

from __future__ import annotations

import logging

from api.ws_handler import ConnectionManager
from core.market_data import Bar, Quote
from engine.engine import Engine
from providers.base import BaseProvider
from state.market_state import MarketState
from state.persistence import StateStore

logger = logging.getLogger(__name__)


async def consume_quotes(
    provider: BaseProvider,
    symbols: list[str],
    state: MarketState,
    ws_manager: ConnectionManager,
    *,
    store: StateStore | None = None,
) -> None:
    """Quote loop: update state + persist + broadcast. No engine involvement."""
    try:
        async for quote in provider.subscribe_quotes(symbols):
            state.update_quote(quote)
            if store is not None and store.enabled:
                try:
                    store.save_quote(quote)
                except Exception:
                    logger.exception("Failed to persist quote")
            await ws_manager.broadcast("quote_update", quote)
    except Exception:
        logger.exception("consume_quotes crashed")


async def consume_bars(
    provider: BaseProvider,
    symbols: list[str],
    timeframe: str,
    engine: Engine,
    ws_manager: ConnectionManager,
    *,
    store: StateStore | None = None,
) -> None:
    """Bar loop: engine.on_bar handles state update + evaluation."""
    try:
        async for bar in provider.subscribe_bars(symbols, timeframe):
            new_candidates = engine.on_bar(bar)
            if store is not None and store.enabled:
                try:
                    store.save_bar(bar)
                except Exception:
                    logger.exception("Failed to persist bar")
            await ws_manager.broadcast("bar_update", bar)
            if new_candidates:
                await ws_manager.broadcast("candidates_update", new_candidates)
    except Exception:
        logger.exception("consume_bars crashed")
