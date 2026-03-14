"""Tactical Asset Allocation — Faber-style trend filter + monthly rebalance (Plan 263).

Long-only, equal-weight across assets with close > SMA. Cash when signal OFF.
"""

from __future__ import annotations

from datetime import datetime

from strategizer.base import Strategy
from strategizer.protocol import ContractSpecView, PortfolioView, Requirements
from strategizer.types import BarInput, Signal


def _sma(closes: list[float], period: int) -> float:
    if len(closes) < period:
        return sum(closes) / len(closes) if closes else 0.0
    return sum(closes[-period:]) / period


class TacticalAssetAllocationStrategy(Strategy):
    """Faber TAA: hold when close > SMA, go to cash when not. Equal-weight. Monthly rebalance."""

    def __init__(
        self,
        symbols: list[str] | None = None,
        sma_period: int = 200,
        timeframe: str = "1d",
    ) -> None:
        self._symbols = symbols or ["SPY"]
        self._sma_period = sma_period
        self._timeframe = timeframe

    @property
    def name(self) -> str:
        return "tactical_asset_allocation"

    def requirements(self) -> Requirements:
        return Requirements(
            symbols=self._symbols,
            timeframes=[self._timeframe],
            lookback=self._sma_period + 10,
            needs_quotes=False,
        )

    def evaluate(
        self,
        ts: datetime,
        bars_by_symbol: dict[str, dict[str, list[BarInput]]],
        specs: dict[str, ContractSpecView],
        portfolio: PortfolioView,
        *,
        step_index: int | None = None,
        strategy_params: dict | None = None,
        option_chain: list[str] | None = None,
    ) -> list[Signal]:
        params = strategy_params or {}
        sma_period = int(params.get("sma_period", self._sma_period))
        timeframe = str(params.get("timeframe", self._timeframe))

        results: list[Signal] = []
        positions = portfolio.get_positions()
        equity = portfolio.get_equity()

        # Detect rebalance day: first bar of new month (month changed from previous bar)
        first_symbol = self._symbols[0] if self._symbols else None
        bars = (bars_by_symbol.get(first_symbol) or {}).get(timeframe, []) if first_symbol else []
        if len(bars) < 2:
            return results
        if bars[-1].ts.month == bars[-2].ts.month:
            return results

        # Compute signal ON/OFF per symbol
        active: list[tuple[str, float]] = []
        for sym in self._symbols:
            sym_bars = (bars_by_symbol.get(sym) or {}).get(timeframe, [])
            if len(sym_bars) < sma_period:
                continue
            closes = [b.close for b in sym_bars]
            ma = _sma(closes, sma_period)
            close = sym_bars[-1].close
            if close > ma:
                active.append((sym, close))

        # Target allocation
        n_active = len(active)
        if n_active == 0:
            # All off: sell everything
            for sym in self._symbols:
                pos = positions.get(sym)
                if pos is None or pos.qty <= 0:
                    continue
                sell_qty = pos.qty
                if sell_qty > 0:
                    results.append(
                        Signal(
                            symbol=sym,
                            direction="SHORT",
                            entry_type="MARKET",
                            entry_price=0.0,
                            stop_price=0.0,
                            targets=[],
                            qty=sell_qty,
                            instrument_id=sym,
                        )
                    )
            return results

        target_dollars = equity / n_active
        for sym, price in active:
            if price <= 0:
                continue
            target_qty = int(target_dollars / price)
            if target_qty <= 0:
                target_qty = 0
            pos = positions.get(sym)
            current_qty = pos.qty if pos else 0
            delta = target_qty - current_qty
            if delta > 0:
                results.append(
                    Signal(
                        symbol=sym,
                        direction="LONG",
                        entry_type="MARKET",
                        entry_price=0.0,
                        stop_price=0.0,
                        targets=[],
                        qty=delta,
                        instrument_id=sym,
                    )
                )
            elif delta < 0:
                sell_qty = min(-delta, current_qty)
                if sell_qty > 0:
                    results.append(
                        Signal(
                            symbol=sym,
                            direction="SHORT",
                            entry_type="MARKET",
                            entry_price=0.0,
                            stop_price=0.0,
                            targets=[],
                            qty=sell_qty,
                            instrument_id=sym,
                        )
                    )

        for sym in self._symbols:
            if any(s[0] == sym for s in active):
                continue
            pos = positions.get(sym)
            if pos is None or pos.qty <= 0:
                continue
            sell_qty = pos.qty
            if sell_qty > 0:
                results.append(
                    Signal(
                        symbol=sym,
                        direction="SHORT",
                        entry_type="MARKET",
                        entry_price=0.0,
                        stop_price=0.0,
                        targets=[],
                        qty=sell_qty,
                        instrument_id=sym,
                    )
                )
        return results
