"""Tests for api.serializers — dataclass → dict helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from core.candidate import Direction, EntryType, TradeCandidate
from core.market_data import Bar, DataQuality, Quote

from api.serializers import (
    serialize_bar,
    serialize_candidate,
    serialize_quote,
    serialize_snapshot,
)


def _make_quote() -> Quote:
    return Quote(
        symbol="ESH26",
        bid=5400.0,
        ask=5400.25,
        last=5400.0,
        bid_size=100,
        ask_size=120,
        volume=50000,
        timestamp=datetime(2026, 2, 24, 14, 30, 0, tzinfo=timezone.utc),
        source="sim",
        quality=DataQuality.OK,
    )


def _make_bar() -> Bar:
    return Bar(
        symbol="ESH26",
        timeframe="5m",
        open=5400.0,
        high=5402.0,
        low=5398.0,
        close=5401.0,
        volume=1200,
        timestamp=datetime(2026, 2, 24, 14, 35, 0, tzinfo=timezone.utc),
        source="sim",
        quality=DataQuality.OK,
    )


def _make_candidate() -> TradeCandidate:
    return TradeCandidate(
        id="abc-123",
        symbol="ESH26",
        strategy="dummy",
        direction=Direction.LONG,
        entry_type=EntryType.STOP,
        entry_price=5402.0,
        stop_price=5398.0,
        targets=[5410.0, 5420.0],
        score=75.0,
        explain=["breakout above range"],
        valid_until=datetime(2026, 2, 24, 15, 0, 0, tzinfo=timezone.utc),
        tags={"tf": "5m"},
        created_at=datetime(2026, 2, 24, 14, 35, 0, tzinfo=timezone.utc),
    )


class TestSerializeQuote:
    def test_returns_dict(self) -> None:
        result = serialize_quote(_make_quote())
        assert isinstance(result, dict)

    def test_contains_all_fields(self) -> None:
        result = serialize_quote(_make_quote())
        expected_keys = {
            "symbol", "bid", "ask", "last", "bid_size", "ask_size",
            "volume", "timestamp", "source", "quality",
        }
        assert set(result.keys()) == expected_keys

    def test_timestamp_is_iso_string(self) -> None:
        result = serialize_quote(_make_quote())
        assert isinstance(result["timestamp"], str)
        assert "2026-02-24" in result["timestamp"]

    def test_quality_is_string(self) -> None:
        result = serialize_quote(_make_quote())
        assert result["quality"] == "OK"

    def test_numeric_values_preserved(self) -> None:
        result = serialize_quote(_make_quote())
        assert result["bid"] == 5400.0
        assert result["ask"] == 5400.25
        assert result["volume"] == 50000


class TestSerializeBar:
    def test_returns_dict(self) -> None:
        result = serialize_bar(_make_bar())
        assert isinstance(result, dict)

    def test_contains_all_fields(self) -> None:
        result = serialize_bar(_make_bar())
        expected_keys = {
            "symbol", "timeframe", "open", "high", "low", "close",
            "volume", "timestamp", "source", "quality",
        }
        assert set(result.keys()) == expected_keys

    def test_timestamp_is_iso_string(self) -> None:
        result = serialize_bar(_make_bar())
        assert isinstance(result["timestamp"], str)

    def test_quality_is_string(self) -> None:
        result = serialize_bar(_make_bar())
        assert result["quality"] == "OK"


class TestSerializeCandidate:
    def test_returns_dict(self) -> None:
        result = serialize_candidate(_make_candidate())
        assert isinstance(result, dict)

    def test_contains_all_fields(self) -> None:
        result = serialize_candidate(_make_candidate())
        expected_keys = {
            "id", "symbol", "strategy", "direction", "entry_type",
            "entry_price", "stop_price", "targets", "score", "explain",
            "valid_until", "tags", "created_at",
        }
        assert set(result.keys()) == expected_keys

    def test_direction_is_string(self) -> None:
        result = serialize_candidate(_make_candidate())
        assert result["direction"] == "LONG"

    def test_entry_type_is_string(self) -> None:
        result = serialize_candidate(_make_candidate())
        assert result["entry_type"] == "STOP"

    def test_timestamps_are_iso_strings(self) -> None:
        result = serialize_candidate(_make_candidate())
        assert isinstance(result["valid_until"], str)
        assert isinstance(result["created_at"], str)

    def test_targets_preserved(self) -> None:
        result = serialize_candidate(_make_candidate())
        assert result["targets"] == [5410.0, 5420.0]


class TestSerializeSnapshot:
    def test_returns_dict_with_expected_keys(self) -> None:
        from state.context import MarketSnapshot

        snapshot = MarketSnapshot(
            timestamp=datetime(2026, 2, 24, 14, 35, 0, tzinfo=timezone.utc),
            quotes={"ESH26": _make_quote()},
            bars={"ESH26": {"5m": [_make_bar()]}},
        )
        candidates = [_make_candidate()]

        result = serialize_snapshot(snapshot, candidates)
        assert set(result.keys()) == {"quotes", "bars", "candidates"}

    def test_quotes_keyed_by_symbol(self) -> None:
        from state.context import MarketSnapshot

        snapshot = MarketSnapshot(
            timestamp=datetime(2026, 2, 24, 14, 35, 0, tzinfo=timezone.utc),
            quotes={"ESH26": _make_quote()},
            bars={},
        )
        result = serialize_snapshot(snapshot, [])
        assert "ESH26" in result["quotes"]
        assert isinstance(result["quotes"]["ESH26"], dict)

    def test_bars_nested_by_symbol_and_timeframe(self) -> None:
        from state.context import MarketSnapshot

        snapshot = MarketSnapshot(
            timestamp=datetime(2026, 2, 24, 14, 35, 0, tzinfo=timezone.utc),
            quotes={},
            bars={"ESH26": {"5m": [_make_bar()]}},
        )
        result = serialize_snapshot(snapshot, [])
        assert "ESH26" in result["bars"]
        assert "5m" in result["bars"]["ESH26"]
        assert isinstance(result["bars"]["ESH26"]["5m"], list)
        assert len(result["bars"]["ESH26"]["5m"]) == 1

    def test_candidates_is_list_of_dicts(self) -> None:
        from state.context import MarketSnapshot

        snapshot = MarketSnapshot(
            timestamp=datetime(2026, 2, 24, 14, 35, 0, tzinfo=timezone.utc),
            quotes={},
            bars={},
        )
        result = serialize_snapshot(snapshot, [_make_candidate()])
        assert isinstance(result["candidates"], list)
        assert len(result["candidates"]) == 1
        assert isinstance(result["candidates"][0], dict)

    def test_empty_state(self) -> None:
        from state.context import MarketSnapshot

        snapshot = MarketSnapshot(
            timestamp=datetime(2026, 2, 24, 14, 35, 0, tzinfo=timezone.utc),
            quotes={},
            bars={},
        )
        result = serialize_snapshot(snapshot, [])
        assert result["quotes"] == {}
        assert result["bars"] == {}
        assert result["candidates"] == []
