"""SimProvider — fake market data for development and testing.

Deterministic seeded random-walk price generator. Emits canonical Quote/Bar
streams at configurable intervals. Allows the full pipeline (provider -> state
-> engine -> API) to run without a real brokerage connection.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from datetime import datetime, time, timezone

from core.instrument import ContractSpec, InstrumentType, TradingSession
from core.market_data import Bar, DataQuality, Quote

from .base import BaseProvider, ProviderHealth

_DEFAULT_SYMBOLS = ["ESH26", "NQM26"]
_DEFAULT_BASE_PRICES: dict[str, float] = {"ESH26": 5400.0, "NQM26": 19500.0}

_ES_RTH = TradingSession(
    name="ES_RTH",
    start_time=time(9, 30),
    end_time=time(16, 0),
    timezone="US/Eastern",
)

_NQ_RTH = TradingSession(
    name="NQ_RTH",
    start_time=time(9, 30),
    end_time=time(16, 0),
    timezone="US/Eastern",
)

_DEFAULT_SPECS: dict[str, ContractSpec] = {
    "ESH26": ContractSpec(
        symbol="ESH26",
        instrument_type=InstrumentType.FUTURE,
        tick_size=0.25,
        point_value=50.0,
        session=_ES_RTH,
    ),
    "NQM26": ContractSpec(
        symbol="NQM26",
        instrument_type=InstrumentType.FUTURE,
        tick_size=0.25,
        point_value=20.0,
        session=_NQ_RTH,
    ),
}


def _walk_price(rng: random.Random, current: float, tick_size: float) -> float:
    """Random walk: move 0-3 ticks in either direction.

    Reasoning: Simple enough for UI dev; seeded RNG ensures determinism.
    """
    ticks = rng.randint(-3, 3)
    return round(current + ticks * tick_size, 10)


class SimProvider(BaseProvider):
    """Fake market data provider for development and testing.

    Reasoning: Deterministic seeded random-walk price generator. Emits
    canonical Quote/Bar streams at configurable intervals. Allows the
    full pipeline (provider -> state -> engine -> API) to run without
    a real brokerage connection.
    """

    def __init__(
        self,
        symbols: list[str] | None = None,
        base_prices: dict[str, float] | None = None,
        quote_interval: float = 0.1,
        bar_interval: float = 60.0,
        seed: int = 42,
    ) -> None:
        self._symbols = symbols or list(_DEFAULT_SYMBOLS)
        self._base_prices = dict(base_prices or _DEFAULT_BASE_PRICES)
        self._quote_interval = quote_interval
        self._bar_interval = bar_interval
        self._seed = seed
        self._connected = False
        self._last_heartbeat: datetime | None = None

    async def connect(self) -> None:
        self._connected = True
        self._last_heartbeat = datetime.now(timezone.utc)

    async def subscribe_quotes(self, symbols: list[str]) -> AsyncIterator[Quote]:
        rng = random.Random(self._seed)
        prices = {s: self._base_prices.get(s, 5000.0) for s in symbols}
        tick = 0.25
        volume = 1_000_000

        while self._connected:
            for sym in symbols:
                if not self._connected:
                    return
                mid = _walk_price(rng, prices[sym], tick)
                prices[sym] = mid
                spread = tick * rng.randint(1, 3)
                bid = round(mid - spread / 2, 10)
                ask = round(mid + spread / 2, 10)
                volume += rng.randint(-5000, 5000)
                volume = max(0, volume)

                yield Quote(
                    symbol=sym,
                    bid=bid,
                    ask=ask,
                    last=mid,
                    bid_size=rng.randint(10, 500),
                    ask_size=rng.randint(10, 500),
                    volume=volume,
                    timestamp=datetime.now(timezone.utc),
                    source="sim",
                    quality=DataQuality.OK,
                )
                self._last_heartbeat = datetime.now(timezone.utc)

            if self._quote_interval > 0:
                await asyncio.sleep(self._quote_interval)

    async def subscribe_bars(
        self, symbols: list[str], timeframe: str
    ) -> AsyncIterator[Bar]:
        rng = random.Random(self._seed + 1)
        prices = {s: self._base_prices.get(s, 5000.0) for s in symbols}
        tick = 0.25

        while self._connected:
            for sym in symbols:
                if not self._connected:
                    return
                o = prices[sym]
                moves = [_walk_price(rng, o, tick) for _ in range(4)]
                h = max(o, *moves)
                l = min(o, *moves)
                c = moves[-1]
                prices[sym] = c

                yield Bar(
                    symbol=sym,
                    timeframe=timeframe,
                    open=o,
                    high=h,
                    low=l,
                    close=c,
                    volume=rng.randint(10_000, 100_000),
                    timestamp=datetime.now(timezone.utc),
                    source="sim",
                    quality=DataQuality.OK,
                )
                self._last_heartbeat = datetime.now(timezone.utc)

            if self._bar_interval > 0:
                await asyncio.sleep(self._bar_interval)

    async def disconnect(self) -> None:
        self._connected = False

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            connected=self._connected,
            source="sim",
            last_heartbeat=self._last_heartbeat,
            message="OK" if self._connected else "Disconnected",
        )

    def get_contract_specs(self) -> dict[str, ContractSpec]:
        return {
            sym: _DEFAULT_SPECS[sym]
            for sym in self._symbols
            if sym in _DEFAULT_SPECS
        }
