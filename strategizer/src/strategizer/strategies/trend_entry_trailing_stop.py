"""trend_entry_trailing_stop — first-cross MA entry + broker-managed trailing stop (Plan 150).

Emits on first bar where low crosses above MA (LONG) or high crosses below MA (SHORT).
Exit is broker-managed trailing stop; strategy includes trailing_stop_ticks in Signal.
"""

from __future__ import annotations

from datetime import datetime

from strategizer.base import Strategy
from strategizer.protocol import ContractSpecView, PortfolioView, Requirements
from strategizer.types import BarInput, Signal


def _sma(closes: list[float], period: int) -> float:
    """Simple moving average of last `period` closes."""
    if len(closes) < period:
        return sum(closes) / len(closes) if closes else 0.0
    return sum(closes[-period:]) / period


class TrendEntryTrailingStopStrategy(Strategy):
    """First-cross MA entry with trailing stop. Stateless except cross detection."""

    def __init__(
        self,
        symbols: list[str] | None = None,
        ma_period: int = 125,
        trailing_stop_ticks: int = 50,
        qty: int = 1,
        direction: str = "LONG",
        timeframe: str = "1m",
    ) -> None:
        self._symbols = symbols or ["ESH1"]
        self._ma_period = ma_period
        self._trailing_stop_ticks = trailing_stop_ticks
        self._qty = qty
        self._direction = direction.upper()
        self._timeframe = timeframe

    @property
    def name(self) -> str:
        return "trend_entry_trailing_stop"

    def requirements(self) -> Requirements:
        return Requirements(
            symbols=self._symbols,
            timeframes=[self._timeframe],
            lookback=max(self._ma_period + 2, 30),
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
        ma_period = int(params.get("ma_period", self._ma_period))
        trailing_stop_ticks = int(params.get("trailing_stop_ticks", self._trailing_stop_ticks))
        qty = int(params.get("qty", self._qty))
        direction = str(params.get("direction", self._direction)).upper()
        timeframe = str(params.get("timeframe", self._timeframe))

        results: list[Signal] = []
        for symbol in self._symbols:
            bars = bars_by_symbol.get(symbol, {}).get(timeframe, [])
            if len(bars) < ma_period + 1:
                continue
            closes = [b.close for b in bars]
            ma = _sma(closes, ma_period)
            prev_low = bars[-2].low
            curr_low = bars[-1].low
            prev_high = bars[-2].high
            curr_high = bars[-1].high

            if direction == "LONG":
                if prev_low < ma and curr_low >= ma:
                    results.append(
                        Signal(
                            symbol=symbol,
                            direction="LONG",
                            entry_type="MARKET",
                            entry_price=0.0,
                            stop_price=0.0,
                            targets=[],
                            qty=qty,
                            instrument_id=None,
                            score=50.0,
                            explain=[f"Bar low cross above {ma_period}-period MA ({ma:.2f})"],
                            valid_until=None,
                            trailing_stop_ticks=trailing_stop_ticks,
                        )
                    )
            elif direction == "SHORT":
                if prev_high > ma and curr_high <= ma:
                    results.append(
                        Signal(
                            symbol=symbol,
                            direction="SHORT",
                            entry_type="MARKET",
                            entry_price=0.0,
                            stop_price=0.0,
                            targets=[],
                            qty=qty,
                            instrument_id=None,
                            score=50.0,
                            explain=[f"Bar high cross below {ma_period}-period MA ({ma:.2f})"],
                            valid_until=None,
                            trailing_stop_ticks=trailing_stop_ticks,
                        )
                    )
        return results
