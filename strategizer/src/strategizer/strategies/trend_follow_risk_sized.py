"""trend_follow_risk_sized — portfolio-aware MA-cross entry + risk-based sizing (Plan 255).

Same MA-cross signal as trend_entry_trailing_stop, but:
- No re-entry when already positioned (get_positions)
- Qty sized by risk budget (get_equity)
- Cash sufficiency guard (get_cash)
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


class TrendFollowRiskSizedStrategy(Strategy):
    """MA-cross entry with risk-based sizing and portfolio guards."""

    def __init__(
        self,
        symbols: list[str] | None = None,
        ma_period: int = 20,
        trailing_stop_ticks: int = 10,
        direction: str = "LONG",
        timeframe: str = "1m",
        risk_pct: float = 0.01,
        max_qty: int = 10,
    ) -> None:
        self._symbols = symbols or ["ES"]
        self._ma_period = ma_period
        self._trailing_stop_ticks = trailing_stop_ticks
        self._direction = direction.upper()
        self._timeframe = timeframe
        self._risk_pct = risk_pct
        self._max_qty = max_qty

    @property
    def name(self) -> str:
        return "trend_follow_risk_sized"

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
        direction = str(params.get("direction", self._direction)).upper()
        timeframe = str(params.get("timeframe", self._timeframe))
        risk_pct = float(params.get("risk_pct", self._risk_pct))
        max_qty = int(params.get("max_qty", self._max_qty))

        results: list[Signal] = []
        for symbol in self._symbols:
            bars = bars_by_symbol.get(symbol, {}).get(timeframe, [])
            if len(bars) < ma_period + 1:
                continue

            # No re-entry when already positioned
            positions = portfolio.get_positions()
            if symbol in positions:
                continue

            spec = specs.get(symbol)
            if spec is None:
                continue
            tick_size = spec.tick_size
            point_value = spec.point_value
            current_price = bars[-1].close

            # Risk-based quantity sizing
            equity = portfolio.get_equity()
            risk_dollars = risk_pct * equity
            stop_distance = trailing_stop_ticks * tick_size
            stop_dollars = stop_distance * point_value
            if stop_dollars <= 0:
                qty = 1
            else:
                qty = int(risk_dollars / stop_dollars)
            qty = max(1, min(qty, max_qty))

            # Cash sufficiency guard
            cost_per_contract = current_price * point_value
            estimated_cost = qty * cost_per_contract
            if portfolio.get_cash() < estimated_cost:
                qty = int(portfolio.get_cash() / cost_per_contract)
            if qty <= 0:
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
                            explain=[
                                f"Bar low cross above {ma_period}-period MA ({ma:.2f}), "
                                f"risk-sized qty={qty}"
                            ],
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
                            explain=[
                                f"Bar high cross below {ma_period}-period MA ({ma:.2f}), "
                                f"risk-sized qty={qty}"
                            ],
                            valid_until=None,
                            trailing_stop_ticks=trailing_stop_ticks,
                        )
                    )
        return results
