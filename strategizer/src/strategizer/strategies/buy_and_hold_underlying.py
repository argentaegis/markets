"""BuyAndHoldUnderlying — buy shares of symbol on step 1, hold until run end."""

from __future__ import annotations

from strategizer.base import Strategy
from strategizer.protocol import ContractSpecView, PortfolioView, Requirements
from strategizer.types import BarInput, Signal


class BuyAndHoldUnderlyingStrategy(Strategy):
    """Buy underlying symbol on step_index 1, hold until run end. Stateless."""

    @property
    def name(self) -> str:
        return "buy_and_hold_underlying"

    def requirements(self) -> Requirements:
        return Requirements(symbols=[], timeframes=[], lookback=0, needs_quotes=False)

    def evaluate(
        self,
        ts,
        bars_by_symbol: dict[str, dict[str, list[BarInput]]],
        specs: dict[str, ContractSpecView],
        portfolio: PortfolioView,
        step_index: int | None = None,
        strategy_params: dict | None = None,
    ) -> list[Signal]:
        params = strategy_params or {}
        if step_index != 1:
            return []

        symbol = params.get("symbol")
        if not symbol:
            return []

        qty = int(params.get("qty", 100))

        return [
            Signal(
                symbol=symbol,
                direction="LONG",
                entry_type="MARKET",
                entry_price=0.0,
                stop_price=0.0,
                targets=[],
                qty=qty,
                instrument_id=None,
            )
        ]
