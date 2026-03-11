"""CoveredCall — buy option on step 1, sell on step exit_step."""

from __future__ import annotations

from strategizer.base import Strategy
from strategizer.protocol import ContractSpecView, PortfolioView, Requirements
from strategizer.types import BarInput, Signal


class CoveredCallStrategy(Strategy):
    """Buy option on step 1, sell on step exit_step. Stateless."""

    @property
    def name(self) -> str:
        return "covered_call"

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
        contract_id = params.get("contract_id")
        if not contract_id:
            return []

        exit_step = int(params.get("exit_step", 3))
        qty = int(params.get("qty", 1))

        if step_index == 1:
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
        if step_index == exit_step:
            return [
                Signal(
                    symbol="",
                    direction="SHORT",
                    entry_type="MARKET",
                    entry_price=0.0,
                    stop_price=0.0,
                    targets=[],
                    qty=qty,
                    instrument_id=contract_id,
                )
            ]
        return []
