"""ORB strategy — Opening Range Breakout on 1m bars.

Identifies the opening range from the first 5 minutes of the RTH session:
- First 5 bars (9:31–9:35) aggregated into OR high/low

Emits Signals when price breaks above or below that range.
Stateless: derives OR and fired state from bars on each request.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from strategizer.base import Strategy
from strategizer.protocol import ContractSpecView, PortfolioView, Requirements
from strategizer.tick import normalize_price, ticks_between
from strategizer.types import BarInput, Signal


def _to_time(v: str | time) -> time:
    """Convert HH:MM:SS string or time to time."""
    if isinstance(v, time):
        return v
    parts = str(v).strip().split(":")
    return time(
        int(parts[0]),
        int(parts[1]) if len(parts) > 1 else 0,
        int(parts[2]) if len(parts) > 2 else 0,
    )


class ORB5mStrategy(Strategy):
    """Opening Range Breakout on 1m bars. Fully stateless."""

    def __init__(
        self,
        symbols: list[str] | None = None,
        min_range_ticks: int = 4,
        max_range_ticks: int = 40,
        qty: int = 1,
    ) -> None:
        self._symbols = symbols or ["ESH1"]
        self._min_range_ticks = min_range_ticks
        self._max_range_ticks = max_range_ticks
        self._qty = qty

    @property
    def name(self) -> str:
        return "orb_5m"

    def requirements(self) -> Requirements:
        return Requirements(
            symbols=self._symbols,
            timeframes=["1m"],
            lookback=80,
            needs_quotes=False,
        )

    def evaluate(
        self,
        ts: datetime,
        bars_by_symbol: dict[str, dict[str, list[BarInput]]],
        specs: dict[str, ContractSpecView],
        portfolio: PortfolioView,
        step_index: int | None = None,
        strategy_params: dict | None = None,
    ) -> list[Signal]:
        params = strategy_params or {}
        qty = int(params.get("qty", self._qty))
        min_range = int(params.get("min_range_ticks", self._min_range_ticks))
        max_range = int(params.get("max_range_ticks", self._max_range_ticks))

        results: list[Signal] = []
        for symbol in self._symbols:
            spec = specs.get(symbol)
            if spec is None:
                continue
            tf_map = bars_by_symbol.get(symbol, {})
            bars = tf_map.get("1m", [])
            if not bars:
                continue
            results.extend(
                self._evaluate_symbol(
                    ts, symbol, spec, bars, qty, min_range, max_range, use_1m=True
                )
            )
        return results

    def _evaluate_symbol(
        self,
        ts: datetime,
        symbol: str,
        spec: ContractSpecView,
        bars: list[BarInput],
        qty: int,
        min_range_ticks: int,
        max_range_ticks: int,
        *,
        use_1m: bool = False,
    ) -> list[Signal]:
        tz = ZoneInfo(spec.timezone)
        session_start = _to_time(getattr(spec, "start_time", "09:30:00"))
        session_end = _to_time(getattr(spec, "end_time", "16:00:00"))
        last_bar = bars[-1]
        session_date = last_bar.ts.astimezone(tz).date()
        or_high, or_low, or_rejected, or_bar_count = self._identify_or_stateless(
            bars,
            spec,
            tz,
            session_start,
            min_range_ticks,
            max_range_ticks,
            session_date,
            use_1m=use_1m,
        )
        if or_high is None or or_rejected:
            return []
        if not self._is_rth_bar(last_bar, tz, session_start, session_end):
            return []

        rth_bars = [
            b
            for b in bars
            if (session_date is None or b.ts.astimezone(tz).date() == session_date)
            and b.ts.astimezone(tz).time() > session_start
        ]
        prior_bars = rth_bars[or_bar_count:-1]
        fired_long = any(b.close > or_high for b in prior_bars)
        fired_short = any(b.close < or_low for b in prior_bars)

        results: list[Signal] = []
        if last_bar.close > or_high and not fired_long:
            results.append(
                self._build_signal(ts, symbol, spec, or_high, or_low, "LONG", tz, session_end, qty)
            )
        if last_bar.close < or_low and not fired_short:
            results.append(
                self._build_signal(ts, symbol, spec, or_high, or_low, "SHORT", tz, session_end, qty)
            )
        return results

    def _is_rth_bar(
        self,
        bar: BarInput,
        tz: ZoneInfo,
        session_start: time,
        session_end: time,
    ) -> bool:
        local_time = bar.ts.astimezone(tz).time()
        return session_start < local_time <= session_end

    def _identify_or_stateless(
        self,
        bars: list[BarInput],
        spec: ContractSpecView,
        tz: ZoneInfo,
        session_start: time,
        min_range_ticks: int,
        max_range_ticks: int,
        session_date: date | None = None,
        *,
        use_1m: bool = False,
    ) -> tuple[float | None, float | None, bool]:
        """Find opening range. Returns (or_high, or_low, rejected).

        - 5m bars: first RTH bar is the OR.
        - 1m bars: first 5 RTH bars aggregated (high=max, low=min).
        """
        tick = spec.tick_size
        rth_bars = [
            b
            for b in bars
            if (session_date is None or b.ts.astimezone(tz).date() == session_date)
            and b.ts.astimezone(tz).time() > session_start
        ]

        if use_1m:
            if len(rth_bars) < 6:
                return None, None, False, 0
            or_bars = rth_bars[:5]
            or_high = max(b.high for b in or_bars)
            or_low = min(b.low for b in or_bars)
        else:
            if not rth_bars:
                return None, None, False, 0
            or_bars = [rth_bars[0]]
            or_high = or_bars[0].high
            or_low = or_bars[0].low

        range_ticks = ticks_between(or_low, or_high, tick)
        if range_ticks < min_range_ticks or range_ticks > max_range_ticks:
            return None, None, True, 0

        return or_high, or_low, False, 5 if use_1m else 1

    def _build_signal(
        self,
        ts: datetime,
        symbol: str,
        spec: ContractSpecView,
        or_high: float,
        or_low: float,
        direction: str,
        tz: ZoneInfo,
        session_end: time,
        qty: int,
    ) -> Signal:
        tick = spec.tick_size

        if direction == "LONG":
            entry = normalize_price(or_high + tick, tick)
            stop = normalize_price(or_low - tick, tick)
            risk = entry - stop
            t1 = normalize_price(entry + risk, tick)
            t2 = normalize_price(entry + 2 * risk, tick)
            dir_label = "above"
        else:
            entry = normalize_price(or_low - tick, tick)
            stop = normalize_price(or_high + tick, tick)
            risk = stop - entry
            t1 = normalize_price(entry - risk, tick)
            t2 = normalize_price(entry - 2 * risk, tick)
            dir_label = "below"

        valid_until = self._build_valid_until(ts, tz, session_end)
        midpoint = (self._min_range_ticks + self._max_range_ticks) / 2
        range_ticks = ticks_between(or_low, or_high, tick)
        deviation = abs(range_ticks - midpoint) / midpoint if midpoint > 0 else 0
        score = max(30.0, 80.0 - (deviation * 40.0))
        risk_ticks = abs(ticks_between(0, risk, tick))
        risk_dollars = risk * spec.point_value / tick

        explain = [
            f"ORB: price broke {dir_label} opening range",
            f"Opening range: {or_low:.2f} – {or_high:.2f} ({range_ticks} ticks)",
            f"Risk (1R): {risk_ticks} ticks = ${risk_dollars:.2f}",
            f"Entry: {entry:.2f} | Stop: {stop:.2f}",
            f"Targets: T1={t1:.2f} (1R) T2={t2:.2f} (2R)",
        ]

        return Signal(
            symbol=symbol,
            direction=direction,
            entry_type="STOP",
            entry_price=entry,
            stop_price=stop,
            targets=[t1, t2],
            qty=qty,
            instrument_id=None,
            score=score,
            explain=explain,
            valid_until=valid_until,
        )

    def _build_valid_until(
        self,
        timestamp: datetime,
        tz: ZoneInfo,
        session_end: time,
    ) -> datetime:
        local_dt = timestamp.astimezone(tz)
        close_local = datetime(
            local_dt.year,
            local_dt.month,
            local_dt.day,
            session_end.hour,
            session_end.minute,
            tzinfo=tz,
        )
        return close_local.astimezone(timezone.utc)
