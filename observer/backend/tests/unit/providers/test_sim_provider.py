"""Tests for SimProvider — quote stream, bar stream, contract specs, lifecycle.

Uses quote_interval=0 and bar_interval=0 for instant yields in tests.
Async tests use asyncio.run() wrapper (pytest-asyncio unavailable on Python 3.14).
"""

from __future__ import annotations

import asyncio
from datetime import timezone

import pytest

from core.market_data import DataQuality, Quote
from providers.base import BaseProvider
from providers.sim_provider import SimProvider


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _sim(**overrides) -> SimProvider:
    defaults = dict(quote_interval=0, bar_interval=0, seed=42)
    defaults.update(overrides)
    return SimProvider(**defaults)


class TestSimProviderIsProvider:
    def test_isinstance(self):
        assert isinstance(_sim(), BaseProvider)


class TestSubscribeQuotes:
    def test_yields_quotes(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            quotes: list[Quote] = []
            async for q in sim.subscribe_quotes(["ESH26"]):
                quotes.append(q)
                if len(quotes) >= 5:
                    break
            assert len(quotes) == 5

        _run(_test())

    def test_quote_has_correct_symbol(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            async for q in sim.subscribe_quotes(["ESH26"]):
                assert q.symbol == "ESH26"
                break

        _run(_test())

    def test_quote_source_is_sim(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            async for q in sim.subscribe_quotes(["ESH26"]):
                assert q.source == "sim"
                break

        _run(_test())

    def test_quote_quality_is_ok(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            async for q in sim.subscribe_quotes(["ESH26"]):
                assert q.quality == DataQuality.OK
                break

        _run(_test())

    def test_quote_timestamp_is_utc(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            async for q in sim.subscribe_quotes(["ESH26"]):
                assert q.timestamp.tzinfo == timezone.utc
                break

        _run(_test())

    def test_quote_prices_near_base(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            quotes: list[Quote] = []
            async for q in sim.subscribe_quotes(["ESH26"]):
                quotes.append(q)
                if len(quotes) >= 20:
                    break
            for q in quotes:
                assert 5300.0 < q.bid < 5500.0, f"bid {q.bid} out of range"
                assert 5300.0 < q.ask < 5500.0, f"ask {q.ask} out of range"
                assert q.ask >= q.bid, "ask must be >= bid"

        _run(_test())

    def test_quote_prices_vary(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            bids: list[float] = []
            async for q in sim.subscribe_quotes(["ESH26"]):
                bids.append(q.bid)
                if len(bids) >= 10:
                    break
            assert len(set(bids)) > 1, "prices should vary across quotes"

        _run(_test())

    def test_multiple_symbols(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            symbols_seen: set[str] = set()
            count = 0
            async for q in sim.subscribe_quotes(["ESH26", "NQM26"]):
                symbols_seen.add(q.symbol)
                count += 1
                if count >= 20:
                    break
            assert "ESH26" in symbols_seen
            assert "NQM26" in symbols_seen

        _run(_test())

    def test_determinism_same_seed(self):
        async def _test():
            sim_a = _sim(seed=42)
            sim_b = _sim(seed=42)
            await sim_a.connect()
            await sim_b.connect()

            quotes_a: list[Quote] = []
            async for q in sim_a.subscribe_quotes(["ESH26"]):
                quotes_a.append(q)
                if len(quotes_a) >= 10:
                    break

            quotes_b: list[Quote] = []
            async for q in sim_b.subscribe_quotes(["ESH26"]):
                quotes_b.append(q)
                if len(quotes_b) >= 10:
                    break

            for a, b in zip(quotes_a, quotes_b):
                assert a.bid == b.bid
                assert a.ask == b.ask
                assert a.last == b.last

        _run(_test())

    def test_quote_positive_sizes(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            async for q in sim.subscribe_quotes(["ESH26"]):
                assert q.bid_size >= 0
                assert q.ask_size >= 0
                assert q.volume >= 0
                break

        _run(_test())


class TestSubscribeBars:
    def test_yields_bars(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            bars = []
            async for b in sim.subscribe_bars(["ESH26"], "5m"):
                bars.append(b)
                if len(bars) >= 5:
                    break
            assert len(bars) == 5

        _run(_test())

    def test_bar_has_correct_symbol(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            async for b in sim.subscribe_bars(["ESH26"], "5m"):
                assert b.symbol == "ESH26"
                break

        _run(_test())

    def test_bar_timeframe_matches(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            async for b in sim.subscribe_bars(["ESH26"], "5m"):
                assert b.timeframe == "5m"
                break

        _run(_test())

    def test_bar_source_is_sim(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            async for b in sim.subscribe_bars(["ESH26"], "5m"):
                assert b.source == "sim"
                break

        _run(_test())

    def test_bar_quality_is_ok(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            async for b in sim.subscribe_bars(["ESH26"], "5m"):
                assert b.quality == DataQuality.OK
                break

        _run(_test())

    def test_bar_timestamp_is_utc(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            async for b in sim.subscribe_bars(["ESH26"], "5m"):
                assert b.timestamp.tzinfo == timezone.utc
                break

        _run(_test())

    def test_bar_ohlcv_consistency(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            bars = []
            async for b in sim.subscribe_bars(["ESH26"], "5m"):
                bars.append(b)
                if len(bars) >= 20:
                    break
            for b in bars:
                assert b.high >= b.open, f"high {b.high} < open {b.open}"
                assert b.high >= b.close, f"high {b.high} < close {b.close}"
                assert b.high >= b.low, f"high {b.high} < low {b.low}"
                assert b.low <= b.open, f"low {b.low} > open {b.open}"
                assert b.low <= b.close, f"low {b.low} > close {b.close}"
                assert b.volume > 0

        _run(_test())

    def test_bar_multiple_symbols(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            symbols_seen: set[str] = set()
            count = 0
            async for b in sim.subscribe_bars(["ESH26", "NQM26"], "5m"):
                symbols_seen.add(b.symbol)
                count += 1
                if count >= 10:
                    break
            assert "ESH26" in symbols_seen
            assert "NQM26" in symbols_seen

        _run(_test())


class TestGetContractSpecs:
    def test_returns_specs_for_default_symbols(self):
        sim = _sim()
        specs = sim.get_contract_specs()
        assert "ESH26" in specs
        assert "NQM26" in specs

    def test_es_spec_values(self):
        sim = _sim()
        spec = sim.get_contract_specs()["ESH26"]
        assert spec.symbol == "ESH26"
        assert spec.tick_size == 0.25
        assert spec.point_value == 50.0
        assert spec.instrument_type.value == "FUTURE"

    def test_nq_spec_values(self):
        sim = _sim()
        spec = sim.get_contract_specs()["NQM26"]
        assert spec.symbol == "NQM26"
        assert spec.tick_size == 0.25
        assert spec.point_value == 20.0

    def test_spec_has_session(self):
        sim = _sim()
        spec = sim.get_contract_specs()["ESH26"]
        assert spec.session is not None
        assert spec.session.timezone == "US/Eastern"

    def test_custom_symbols_only_known(self):
        sim = SimProvider(symbols=["ESH26"], quote_interval=0, bar_interval=0)
        specs = sim.get_contract_specs()
        assert "ESH26" in specs
        assert "NQM26" not in specs


class TestHealth:
    def test_health_before_connect(self):
        async def _test():
            sim = _sim()
            h = await sim.health()
            assert h.connected is False
            assert h.source == "sim"

        _run(_test())

    def test_health_after_connect(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            h = await sim.health()
            assert h.connected is True
            assert h.source == "sim"
            assert h.last_heartbeat is not None
            assert h.message == "OK"

        _run(_test())

    def test_health_after_disconnect(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            await sim.disconnect()
            h = await sim.health()
            assert h.connected is False

        _run(_test())


class TestDisconnectStopsGenerators:
    def test_quote_generator_stops(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            quotes = []
            async for q in sim.subscribe_quotes(["ESH26"]):
                quotes.append(q)
                if len(quotes) == 3:
                    await sim.disconnect()
            assert len(quotes) <= 5, "generator should stop shortly after disconnect"

        _run(_test())

    def test_bar_generator_stops(self):
        async def _test():
            sim = _sim()
            await sim.connect()
            bars = []
            async for b in sim.subscribe_bars(["ESH26"], "5m"):
                bars.append(b)
                if len(bars) == 3:
                    await sim.disconnect()
            assert len(bars) <= 5, "generator should stop shortly after disconnect"

        _run(_test())
