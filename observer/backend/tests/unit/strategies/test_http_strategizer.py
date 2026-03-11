"""Tests for HttpStrategizerAdapter — HTTP client for Strategizer service."""

from __future__ import annotations

from datetime import datetime, time, timezone
from unittest.mock import patch, MagicMock

import pytest

from core.candidate import Direction, EntryType
from core.instrument import ContractSpec, InstrumentType, TradingSession
from core.market_data import Bar, DataQuality
from state.context import Context

from strategies.http_strategizer import HttpStrategizerAdapter

T0 = datetime(2026, 2, 24, 14, 30, 0, tzinfo=timezone.utc)

ES_SPEC = ContractSpec(
    symbol="ESH26",
    instrument_type=InstrumentType.FUTURE,
    tick_size=0.25,
    point_value=50.0,
    session=TradingSession(
        name="RTH",
        start_time=time(9, 30),
        end_time=time(16, 0),
        timezone="America/New_York",
    ),
)


def _make_bar(
    symbol: str = "ESH26",
    timeframe: str = "5m",
    close: float = 5403.75,
    ts: datetime = T0,
) -> Bar:
    return Bar(
        symbol=symbol,
        timeframe=timeframe,
        open=close - 3.0,
        high=close + 2.0,
        low=close - 4.0,
        close=close,
        volume=45_000,
        timestamp=ts,
        source="sim",
        quality=DataQuality.OK,
    )


class TestHttpStrategizerAdapter:
    def test_name_and_requirements(self) -> None:
        adapter = HttpStrategizerAdapter(strategy_name="orb_5m", strategy_params={"symbols": ["ESH26"]})
        assert adapter.name == "orb_5m"
        req = adapter.requirements()
        assert req.symbols == ["ESH26"]
        assert req.timeframes == ["5m"]
        assert req.lookback == 80

    def test_evaluate_returns_trade_candidates_when_service_returns_signals(self) -> None:
        adapter = HttpStrategizerAdapter(
            strategy_name="orb_5m",
            strategy_params={"symbols": ["ESH26"], "min_range_ticks": 4, "max_range_ticks": 40},
        )
        bar = _make_bar(close=5412.0)
        ctx = Context(
            timestamp=T0,
            quotes={},
            bars={"ESH26": {"5m": [bar]}},
            specs={"ESH26": ES_SPEC},
            portfolio=MagicMock(),
        )

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'[{"symbol":"ESH26","instrument_id":null,"direction":"LONG","entry_type":"STOP","entry_price":5410.5,"stop_price":5400.5,"targets":[5418.5,5426.5],"qty":1,"score":80,"explain":["ORB breakout"],"valid_until":null}]'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = adapter.evaluate(ctx)

        assert len(result) == 1
        assert result[0].tags.get("source") == "strategizer_http"
        assert result[0].symbol == "ESH26"
        assert result[0].strategy == "orb_5m"
        assert result[0].direction == Direction.LONG
        assert result[0].entry_type == EntryType.STOP
        assert result[0].entry_price == 5410.5

    def test_evaluate_returns_empty_when_service_returns_empty_list(self) -> None:
        adapter = HttpStrategizerAdapter(strategy_name="buy_and_hold", strategy_params={"contract_id": "x"})
        ctx = Context(timestamp=T0, quotes={}, bars={}, specs={}, portfolio=MagicMock())

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b"[]"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = adapter.evaluate(ctx)

        assert result == []
