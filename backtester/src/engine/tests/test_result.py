"""BacktestResult and EquityPoint tests — Phase 2 of 070.

Reasoning: BacktestResult collects all engine outputs for Reporter (Step 7)
and golden test (Step 8). EquityPoint records per-step equity for curve.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.domain.config import BacktestConfig
from src.domain.event import Event, EventType
from src.domain.fill import Fill
from src.domain.order import Order
from src.domain.portfolio import PortfolioState
from src.engine.result import BacktestResult, EquityPoint
from src.loader.config import DataProviderConfig


def _utc(year: int, month: int, day: int, hour: int = 0) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def _sample_config() -> BacktestConfig:
    dp = DataProviderConfig(underlying_path=Path("/f"), options_path=Path("/o"))
    return BacktestConfig(
        symbol="SPY",
        start=_utc(2026, 1, 1),
        end=_utc(2026, 1, 31),
        timeframe_base="1d",
        data_provider_config=dp,
    )


def _empty_portfolio() -> PortfolioState:
    return PortfolioState(
        cash=100_000.0,
        positions={},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=100_000.0,
    )


def test_equity_point_holds_ts_and_equity() -> None:
    """EquityPoint stores timestamp and equity value."""
    ts = _utc(2026, 1, 2, 21)
    ep = EquityPoint(ts=ts, equity=100_000.0)
    assert ep.ts == ts
    assert ep.equity == 100_000.0


def test_backtest_result_holds_all_fields() -> None:
    """BacktestResult holds config, equity_curve, orders, fills, events, final_portfolio."""
    config = _sample_config()
    portfolio = _empty_portfolio()
    ts = _utc(2026, 1, 2, 21)

    eq_curve = [EquityPoint(ts=ts, equity=100_000.0)]
    orders = [Order(id="o1", ts=ts, instrument_id="SPY", side="BUY", qty=1, order_type="market")]
    fills = [Fill(order_id="o1", ts=ts, fill_price=480.0, fill_qty=1)]
    events = [Event(ts=ts, type=EventType.MARKET, payload={})]

    result = BacktestResult(
        config=config,
        equity_curve=eq_curve,
        orders=orders,
        fills=fills,
        events=events,
        final_portfolio=portfolio,
    )
    assert result.config is config
    assert len(result.equity_curve) == 1
    assert len(result.orders) == 1
    assert len(result.fills) == 1
    assert len(result.events) == 1
    assert result.final_portfolio is portfolio


def test_backtest_result_empty_is_valid() -> None:
    """Empty result (no trades) is valid — NullStrategy baseline."""
    result = BacktestResult(
        config=_sample_config(),
        equity_curve=[],
        orders=[],
        fills=[],
        events=[],
        final_portfolio=_empty_portfolio(),
    )
    assert result.orders == []
    assert result.fills == []
    assert result.equity_curve == []


def test_backtest_result_field_types() -> None:
    """Fields have correct collection types."""
    result = BacktestResult(
        config=_sample_config(),
        equity_curve=[],
        orders=[],
        fills=[],
        events=[],
        final_portfolio=_empty_portfolio(),
    )
    assert isinstance(result.equity_curve, list)
    assert isinstance(result.orders, list)
    assert isinstance(result.fills, list)
    assert isinstance(result.events, list)
    assert isinstance(result.final_portfolio, PortfolioState)
    assert isinstance(result.config, BacktestConfig)
