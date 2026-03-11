"""ORB5mStrategy — Opening Range Breakout on 5-minute bars.

Identifies the opening range from the first 5-minute bar of the RTH session,
then emits trade candidates when price breaks above or below that range.
Entry via stop order at OR boundary ± 1 tick, stop at opposite boundary,
targets at 1R and 2R.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from core.candidate import Direction, EntryType, TradeCandidate
from core.instrument import ContractSpec
from core.market_data import Bar
from core.tick import normalize_price, ticks_between
from state.context import Context

from .base import BaseStrategy, Requirements

logger = logging.getLogger(__name__)


class ORB5mStrategy(BaseStrategy):
    """Opening Range Breakout on 5-minute bars.

    Tracks the first 5m bar after RTH open as the opening range, then
    generates LONG/SHORT candidates on breakout. One candidate per
    direction per session.
    """

    NAME = "orb_5m"

    def __init__(
        self,
        symbols: list[str] | None = None,
        min_range_ticks: int = 4,
        max_range_ticks: int = 40,
    ) -> None:
        self._symbols = symbols or ["ESH26"]
        self._min_range_ticks = min_range_ticks
        self._max_range_ticks = max_range_ticks

        self._or_high: float | None = None
        self._or_low: float | None = None
        self._session_date: date | None = None
        self._fired: set[Direction] = set()
        self._or_rejected: bool = False

    @property
    def name(self) -> str:
        return self.NAME

    def requirements(self) -> Requirements:
        return Requirements(
            symbols=self._symbols,
            timeframes=["5m"],
            lookback=80,
            needs_quotes=False,
        )

    def evaluate(self, ctx: Context) -> list[TradeCandidate]:
        candidates: list[TradeCandidate] = []
        for symbol in self._symbols:
            spec = ctx.specs.get(symbol)
            if spec is None:
                continue
            bars = ctx.bars.get(symbol, {}).get("5m", [])
            if not bars:
                continue
            candidates.extend(self._evaluate_symbol(ctx, symbol, spec, bars))
        return candidates

    def _evaluate_symbol(
        self,
        ctx: Context,
        symbol: str,
        spec: ContractSpec,
        bars: list[Bar],
    ) -> list[TradeCandidate]:
        tz = ZoneInfo(spec.session.timezone)
        session_start = spec.session.start_time
        session_end = spec.session.end_time

        current_date = self._get_session_date(ctx.timestamp, tz)
        if current_date != self._session_date:
            self._reset_session(current_date)

        if self._or_high is None and not self._or_rejected:
            self._identify_or(bars, spec, tz, session_start)

        if self._or_high is None:
            return []

        last_bar = bars[-1]
        if not self._is_rth_bar(last_bar, tz, session_start, session_end):
            return []

        return self._check_breakout(ctx, last_bar, symbol, spec, tz, session_end)

    def _get_session_date(self, timestamp: datetime, tz: ZoneInfo) -> date:
        return timestamp.astimezone(tz).date()

    def _reset_session(self, session_date: date) -> None:
        self._session_date = session_date
        self._or_high = None
        self._or_low = None
        self._fired = set()
        self._or_rejected = False

    def _is_rth_bar(
        self,
        bar: Bar,
        tz: ZoneInfo,
        session_start: time,
        session_end: time,
    ) -> bool:
        local_time = bar.timestamp.astimezone(tz).time()
        return session_start < local_time <= session_end

    def _identify_or(
        self,
        bars: list[Bar],
        spec: ContractSpec,
        tz: ZoneInfo,
        session_start: time,
    ) -> None:
        """Find the first RTH bar and set the opening range."""
        for bar in bars:
            local_time = bar.timestamp.astimezone(tz).time()
            if local_time <= session_start:
                continue

            tick = spec.tick_size
            range_ticks = ticks_between(bar.low, bar.high, tick)

            if range_ticks < self._min_range_ticks or range_ticks > self._max_range_ticks:
                logger.info(
                    "ORB %s: OR rejected — %d ticks (min=%d, max=%d)",
                    spec.symbol, range_ticks, self._min_range_ticks, self._max_range_ticks,
                )
                self._or_rejected = True
                return

            self._or_high = bar.high
            self._or_low = bar.low
            logger.info(
                "ORB %s: OR identified — high=%.2f low=%.2f (%d ticks)",
                spec.symbol, bar.high, bar.low, range_ticks,
            )
            return

    def _check_breakout(
        self,
        ctx: Context,
        bar: Bar,
        symbol: str,
        spec: ContractSpec,
        tz: ZoneInfo,
        session_end: time,
    ) -> list[TradeCandidate]:
        assert self._or_high is not None and self._or_low is not None
        results: list[TradeCandidate] = []

        if bar.close > self._or_high and Direction.LONG not in self._fired:
            self._fired.add(Direction.LONG)
            results.append(self._build_candidate(
                ctx, symbol, spec, Direction.LONG, tz, session_end, bar,
            ))

        if bar.close < self._or_low and Direction.SHORT not in self._fired:
            self._fired.add(Direction.SHORT)
            results.append(self._build_candidate(
                ctx, symbol, spec, Direction.SHORT, tz, session_end, bar,
            ))

        return results

    def _build_candidate(
        self,
        ctx: Context,
        symbol: str,
        spec: ContractSpec,
        direction: Direction,
        tz: ZoneInfo,
        session_end: time,
        bar: Bar,
    ) -> TradeCandidate:
        assert self._or_high is not None and self._or_low is not None
        tick = spec.tick_size

        if direction == Direction.LONG:
            entry = normalize_price(self._or_high + tick, tick)
            stop = normalize_price(self._or_low - tick, tick)
            risk = entry - stop
            t1 = normalize_price(entry + risk, tick)
            t2 = normalize_price(entry + 2 * risk, tick)
            setup = "breakout_long"
        else:
            entry = normalize_price(self._or_low - tick, tick)
            stop = normalize_price(self._or_high + tick, tick)
            risk = stop - entry
            t1 = normalize_price(entry - risk, tick)
            t2 = normalize_price(entry - 2 * risk, tick)
            setup = "breakout_short"

        valid_until = self._build_valid_until(ctx.timestamp, tz, session_end)
        score = self._compute_score()
        range_ticks = ticks_between(self._or_low, self._or_high, tick)
        risk_ticks = ticks_between(0, risk, tick) if direction == Direction.LONG else ticks_between(0, risk, tick)
        risk_dollars = risk * spec.point_value / tick

        dir_label = "above" if direction == Direction.LONG else "below"
        explain = [
            f"ORB 5m: price broke {dir_label} opening range",
            f"Opening range: {self._or_low:.2f} – {self._or_high:.2f} ({range_ticks} ticks)",
            f"Risk (1R): {risk_ticks} ticks = ${risk_dollars:.2f}",
            f"Entry: {entry:.2f} | Stop: {stop:.2f}",
            f"Targets: T1={t1:.2f} (1R) T2={t2:.2f} (2R)",
        ]

        return TradeCandidate(
            id=str(uuid.uuid4()),
            symbol=symbol,
            strategy=self.name,
            direction=direction,
            entry_type=EntryType.STOP,
            entry_price=entry,
            stop_price=stop,
            targets=[t1, t2],
            score=score,
            explain=explain,
            valid_until=valid_until,
            tags={"strategy": self.name, "setup": setup},
            created_at=ctx.timestamp,
        )

    def _build_valid_until(
        self,
        timestamp: datetime,
        tz: ZoneInfo,
        session_end: time,
    ) -> datetime:
        local_dt = timestamp.astimezone(tz)
        close_local = datetime(
            local_dt.year, local_dt.month, local_dt.day,
            session_end.hour, session_end.minute,
            tzinfo=tz,
        )
        return close_local.astimezone(timezone.utc)

    def _compute_score(self) -> float:
        assert self._or_high is not None and self._or_low is not None
        midpoint = (self._min_range_ticks + self._max_range_ticks) / 2
        range_ticks = ticks_between(self._or_low, self._or_high, 0.25)
        deviation = abs(range_ticks - midpoint) / midpoint if midpoint > 0 else 0
        return max(30.0, 80.0 - (deviation * 40.0))
