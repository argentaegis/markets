"""BuyAndHold — buy one option on step 1, hold until run end."""

from __future__ import annotations

from strategizer.base import Strategy
from strategizer.protocol import ContractSpecView, OptionFetchSpec, PortfolioView, Requirements
from strategizer.types import BarInput, Signal


class BuyAndHoldStrategy(Strategy):
    """Buy one option on step_index 1, hold until run end. Stateless."""

    @property
    def name(self) -> str:
        return "buy_and_hold"

    def requirements(self) -> Requirements:
        return Requirements(symbols=[], timeframes=[], lookback=0, needs_quotes=False)

    def option_fetch_spec(
        self,
        ts,
        portfolio: PortfolioView,
        underlying_close: float | None,
        step_index: int,
        strategy_params: dict,
    ) -> OptionFetchSpec | None:
        contract_id = (strategy_params or {}).get("contract_id")
        if contract_id:
            return OptionFetchSpec(contract_ids=[contract_id])
        return None

    def evaluate(
        self,
        ts,
        bars_by_symbol: dict[str, dict[str, list[BarInput]]],
        specs: dict[str, ContractSpecView],
        portfolio: PortfolioView,
        *,
        step_index: int | None = None,
        strategy_params: dict | None = None,
        option_chain: list[str] | None = None,
    ) -> list[Signal]:
        params = strategy_params or {}
        if step_index != 1:
            return []

        contract_id = params.get("contract_id")
        if not contract_id:
            return []

        qty = int(params.get("qty", 1))

        return [
            Signal(
                symbol="",
                direction="LONG",
                entry_type="MARKET",
                entry_price=0.0,
                stop_price=0.0,
                targets=[],
                qty=qty,
                instrument_id=contract_id,
            )
        ]
