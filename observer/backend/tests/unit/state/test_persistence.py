"""Tests for StateStore — SQLite persistence for quotes and bars."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.market_data import Bar, DataQuality, Quote
from state.persistence import StateStore

T0 = datetime(2026, 2, 24, 14, 30, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 2, 24, 14, 35, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 2, 24, 14, 40, 0, tzinfo=timezone.utc)


def _make_quote(
    symbol: str = "ESH26",
    timestamp: datetime = T0,
) -> Quote:
    return Quote(
        symbol=symbol,
        bid=5400.25,
        ask=5400.50,
        last=5400.25,
        bid_size=120,
        ask_size=85,
        volume=1_200_000,
        timestamp=timestamp,
        source="sim",
        quality=DataQuality.OK,
    )


def _make_bar(
    symbol: str = "ESH26",
    timeframe: str = "5m",
    timestamp: datetime = T0,
) -> Bar:
    return Bar(
        symbol=symbol,
        timeframe=timeframe,
        open=5400.00,
        high=5405.25,
        low=5398.50,
        close=5403.75,
        volume=45_000,
        timestamp=timestamp,
        source="sim",
        quality=DataQuality.OK,
    )


class TestDisabled:
    def test_disabled_when_db_path_none(self):
        store = StateStore(db_path=None)
        assert store.enabled is False

    def test_save_quote_is_noop(self):
        store = StateStore(db_path=None)
        store.save_quote(_make_quote())

    def test_save_bar_is_noop(self):
        store = StateStore(db_path=None)
        store.save_bar(_make_bar())

    def test_get_quotes_returns_empty(self):
        store = StateStore(db_path=None)
        assert store.get_quotes("ESH26") == []

    def test_get_bars_returns_empty(self):
        store = StateStore(db_path=None)
        assert store.get_bars("ESH26", "5m") == []


class TestEnabled:
    def test_enabled_when_db_path_set(self):
        store = StateStore(db_path=":memory:")
        assert store.enabled is True

    def test_tables_created(self):
        import sqlite3

        store = StateStore(db_path=":memory:")
        conn = store._conn
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        assert "bars" in tables
        assert "quotes" in tables


class TestQuoteRoundTrip:
    def test_save_and_get(self):
        store = StateStore(db_path=":memory:")
        q = _make_quote()
        store.save_quote(q)
        result = store.get_quotes("ESH26")
        assert len(result) == 1
        assert result[0].symbol == q.symbol
        assert result[0].bid == q.bid
        assert result[0].ask == q.ask
        assert result[0].last == q.last
        assert result[0].bid_size == q.bid_size
        assert result[0].ask_size == q.ask_size
        assert result[0].volume == q.volume
        assert result[0].timestamp == q.timestamp
        assert result[0].source == q.source
        assert result[0].quality == q.quality

    def test_filter_by_symbol(self):
        store = StateStore(db_path=":memory:")
        store.save_quote(_make_quote(symbol="ESH26"))
        store.save_quote(_make_quote(symbol="NQH26"))
        result = store.get_quotes("ESH26")
        assert len(result) == 1
        assert result[0].symbol == "ESH26"

    def test_filter_by_since(self):
        store = StateStore(db_path=":memory:")
        store.save_quote(_make_quote(timestamp=T0))
        store.save_quote(_make_quote(timestamp=T1))
        store.save_quote(_make_quote(timestamp=T2))
        result = store.get_quotes("ESH26", since=T1)
        assert len(result) == 2
        assert result[0].timestamp == T1
        assert result[1].timestamp == T2

    def test_multiple_quotes_same_symbol(self):
        store = StateStore(db_path=":memory:")
        store.save_quote(_make_quote(timestamp=T0))
        store.save_quote(_make_quote(timestamp=T1))
        result = store.get_quotes("ESH26")
        assert len(result) == 2


class TestBarRoundTrip:
    def test_save_and_get(self):
        store = StateStore(db_path=":memory:")
        b = _make_bar()
        store.save_bar(b)
        result = store.get_bars("ESH26", "5m")
        assert len(result) == 1
        assert result[0].symbol == b.symbol
        assert result[0].timeframe == b.timeframe
        assert result[0].open == b.open
        assert result[0].high == b.high
        assert result[0].low == b.low
        assert result[0].close == b.close
        assert result[0].volume == b.volume
        assert result[0].timestamp == b.timestamp
        assert result[0].source == b.source
        assert result[0].quality == b.quality

    def test_filter_by_symbol(self):
        store = StateStore(db_path=":memory:")
        store.save_bar(_make_bar(symbol="ESH26"))
        store.save_bar(_make_bar(symbol="NQH26"))
        result = store.get_bars("ESH26", "5m")
        assert len(result) == 1
        assert result[0].symbol == "ESH26"

    def test_filter_by_timeframe(self):
        store = StateStore(db_path=":memory:")
        store.save_bar(_make_bar(timeframe="1m"))
        store.save_bar(_make_bar(timeframe="5m"))
        result = store.get_bars("ESH26", "5m")
        assert len(result) == 1
        assert result[0].timeframe == "5m"

    def test_filter_by_since(self):
        store = StateStore(db_path=":memory:")
        store.save_bar(_make_bar(timestamp=T0))
        store.save_bar(_make_bar(timestamp=T1))
        store.save_bar(_make_bar(timestamp=T2))
        result = store.get_bars("ESH26", "5m", since=T1)
        assert len(result) == 2
        assert result[0].timestamp == T1
        assert result[1].timestamp == T2

    def test_multiple_bars_same_symbol(self):
        store = StateStore(db_path=":memory:")
        store.save_bar(_make_bar(timestamp=T0))
        store.save_bar(_make_bar(timestamp=T1))
        result = store.get_bars("ESH26", "5m")
        assert len(result) == 2

    def test_multiple_symbols_coexist(self):
        store = StateStore(db_path=":memory:")
        store.save_bar(_make_bar(symbol="ESH26", timestamp=T0))
        store.save_bar(_make_bar(symbol="NQH26", timestamp=T0))
        es = store.get_bars("ESH26", "5m")
        nq = store.get_bars("NQH26", "5m")
        assert len(es) == 1
        assert len(nq) == 1
