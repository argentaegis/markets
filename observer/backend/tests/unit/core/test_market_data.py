"""Tests for core market data types — Quote, Bar, DataQuality.

Covers creation, immutability, UTC timestamps, and __post_init__ validation
(NaN rejection, negative volume rejection).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from core.market_data import Bar, DataQuality, Quote


class TestDataQuality:
    def test_has_ok(self):
        assert DataQuality.OK.value == "OK"

    def test_has_stale(self):
        assert DataQuality.STALE.value == "STALE"

    def test_has_missing(self):
        assert DataQuality.MISSING.value == "MISSING"

    def test_has_partial(self):
        assert DataQuality.PARTIAL.value == "PARTIAL"


NOW_UTC = datetime(2026, 2, 24, 14, 35, 0, tzinfo=timezone.utc)


class TestQuote:
    def test_creation(self):
        q = Quote(
            symbol="ESH26",
            bid=5400.25,
            ask=5400.50,
            last=5400.25,
            bid_size=120,
            ask_size=85,
            volume=1_200_000,
            timestamp=NOW_UTC,
            source="sim",
            quality=DataQuality.OK,
        )
        assert q.symbol == "ESH26"
        assert q.bid == 5400.25
        assert q.ask == 5400.50
        assert q.last == 5400.25
        assert q.bid_size == 120
        assert q.ask_size == 85
        assert q.volume == 1_200_000
        assert q.timestamp == NOW_UTC
        assert q.source == "sim"
        assert q.quality == DataQuality.OK

    def test_immutability(self):
        q = Quote(
            symbol="ESH26",
            bid=5400.25,
            ask=5400.50,
            last=5400.25,
            bid_size=120,
            ask_size=85,
            volume=1_200_000,
            timestamp=NOW_UTC,
            source="sim",
            quality=DataQuality.OK,
        )
        with pytest.raises(AttributeError):
            q.bid = 5401.0

    def test_timestamp_is_utc(self):
        q = Quote(
            symbol="ESH26",
            bid=5400.25,
            ask=5400.50,
            last=5400.25,
            bid_size=120,
            ask_size=85,
            volume=1_200_000,
            timestamp=NOW_UTC,
            source="sim",
            quality=DataQuality.OK,
        )
        assert q.timestamp.tzinfo == timezone.utc

    def test_rejects_nan_bid(self):
        with pytest.raises(ValueError, match="bid"):
            Quote(
                symbol="ESH26",
                bid=float("nan"),
                ask=5400.50,
                last=5400.25,
                bid_size=120,
                ask_size=85,
                volume=1_200_000,
                timestamp=NOW_UTC,
                source="sim",
                quality=DataQuality.OK,
            )

    def test_rejects_nan_ask(self):
        with pytest.raises(ValueError, match="ask"):
            Quote(
                symbol="ESH26",
                bid=5400.25,
                ask=float("nan"),
                last=5400.25,
                bid_size=120,
                ask_size=85,
                volume=1_200_000,
                timestamp=NOW_UTC,
                source="sim",
                quality=DataQuality.OK,
            )

    def test_rejects_nan_last(self):
        with pytest.raises(ValueError, match="last"):
            Quote(
                symbol="ESH26",
                bid=5400.25,
                ask=5400.50,
                last=float("nan"),
                bid_size=120,
                ask_size=85,
                volume=1_200_000,
                timestamp=NOW_UTC,
                source="sim",
                quality=DataQuality.OK,
            )

    def test_rejects_negative_volume(self):
        with pytest.raises(ValueError, match="volume"):
            Quote(
                symbol="ESH26",
                bid=5400.25,
                ask=5400.50,
                last=5400.25,
                bid_size=120,
                ask_size=85,
                volume=-1,
                timestamp=NOW_UTC,
                source="sim",
                quality=DataQuality.OK,
            )

    def test_rejects_negative_bid_size(self):
        with pytest.raises(ValueError, match="bid_size"):
            Quote(
                symbol="ESH26",
                bid=5400.25,
                ask=5400.50,
                last=5400.25,
                bid_size=-1,
                ask_size=85,
                volume=1_200_000,
                timestamp=NOW_UTC,
                source="sim",
                quality=DataQuality.OK,
            )


class TestBar:
    def test_creation(self):
        b = Bar(
            symbol="ESH26",
            timeframe="5m",
            open=5400.00,
            high=5405.25,
            low=5398.50,
            close=5403.75,
            volume=45_000,
            timestamp=NOW_UTC,
            source="sim",
            quality=DataQuality.OK,
        )
        assert b.symbol == "ESH26"
        assert b.timeframe == "5m"
        assert b.open == 5400.00
        assert b.high == 5405.25
        assert b.low == 5398.50
        assert b.close == 5403.75
        assert b.volume == 45_000
        assert b.timestamp == NOW_UTC

    def test_immutability(self):
        b = Bar(
            symbol="ESH26",
            timeframe="5m",
            open=5400.00,
            high=5405.25,
            low=5398.50,
            close=5403.75,
            volume=45_000,
            timestamp=NOW_UTC,
            source="sim",
            quality=DataQuality.OK,
        )
        with pytest.raises(AttributeError):
            b.close = 5410.0

    def test_rejects_nan_open(self):
        with pytest.raises(ValueError, match="open"):
            Bar(
                symbol="ESH26",
                timeframe="5m",
                open=float("nan"),
                high=5405.25,
                low=5398.50,
                close=5403.75,
                volume=45_000,
                timestamp=NOW_UTC,
                source="sim",
                quality=DataQuality.OK,
            )

    def test_rejects_nan_close(self):
        with pytest.raises(ValueError, match="close"):
            Bar(
                symbol="ESH26",
                timeframe="5m",
                open=5400.00,
                high=5405.25,
                low=5398.50,
                close=float("nan"),
                volume=45_000,
                timestamp=NOW_UTC,
                source="sim",
                quality=DataQuality.OK,
            )

    def test_rejects_negative_volume(self):
        with pytest.raises(ValueError, match="volume"):
            Bar(
                symbol="ESH26",
                timeframe="5m",
                open=5400.00,
                high=5405.25,
                low=5398.50,
                close=5403.75,
                volume=-100,
                timestamp=NOW_UTC,
                source="sim",
                quality=DataQuality.OK,
            )

    def test_zero_volume_ok(self):
        b = Bar(
            symbol="ESH26",
            timeframe="5m",
            open=5400.00,
            high=5400.00,
            low=5400.00,
            close=5400.00,
            volume=0,
            timestamp=NOW_UTC,
            source="sim",
            quality=DataQuality.OK,
        )
        assert b.volume == 0
