"""Integration tests: domain + config and clock (from validation.domain_clock)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.clock import iter_times
from src.domain.config import BacktestConfig
from src.domain.event import Event, EventType
from src.domain.fill import Fill
from src.domain.order import Order
from src.domain.portfolio import PortfolioState
from src.domain.position import Position
from src.loader.provider import DataProviderConfig


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


@pytest.fixture
def domain_clock_config(fixtures_root) -> BacktestConfig:
    """BacktestConfig with fixture paths for domain+clock integration."""
    dp_config = DataProviderConfig(
        underlying_path=fixtures_root / "underlying",
        options_path=fixtures_root / "options",
        missing_data_policy="RETURN_PARTIAL",
    )
    start = _utc(2024, 1, 2, 0, 0)
    end = _utc(2024, 1, 5, 23, 59)
    return BacktestConfig(
        symbol="SPY",
        start=start,
        end=end,
        timeframe_base="1d",
        data_provider_config=dp_config,
        broker="zero",
        seed=42,
    )


@pytest.mark.integration
def test_config_roundtrip(domain_clock_config: BacktestConfig) -> None:
    """BacktestConfig to_dict/from_dict round-trip."""
    restored = BacktestConfig.from_dict(domain_clock_config.to_dict())
    assert restored.symbol == domain_clock_config.symbol
    assert restored.timeframe_base == domain_clock_config.timeframe_base
    assert restored.seed == domain_clock_config.seed


@pytest.mark.integration
def test_iter_times_1d(domain_clock_config: BacktestConfig) -> None:
    """iter_times 1d yields 4 trading days Jan 2-5."""
    ts_1d = list(iter_times(domain_clock_config.start, domain_clock_config.end, "1d"))
    assert len(ts_1d) == 4


@pytest.mark.integration
def test_iter_times_1h(domain_clock_config: BacktestConfig) -> None:
    """iter_times 1h yields 28 hourly bars (4 days × 7 bars/day)."""
    ts_1h = list(iter_times(domain_clock_config.start, domain_clock_config.end, "1h"))
    assert len(ts_1h) == 28


@pytest.mark.integration
def test_iter_times_1m(domain_clock_config: BacktestConfig) -> None:
    """iter_times 1m yields 1560 minute bars (4 × 390)."""
    ts_1m = list(iter_times(domain_clock_config.start, domain_clock_config.end, "1m"))
    assert len(ts_1m) == 4 * 390


@pytest.mark.integration
def test_iter_times_determinism(domain_clock_config: BacktestConfig) -> None:
    """Same inputs yield same sequence."""
    ts_1 = list(iter_times(domain_clock_config.start, domain_clock_config.end, "1d"))
    ts_2 = list(iter_times(domain_clock_config.start, domain_clock_config.end, "1d"))
    assert ts_1 == ts_2


@pytest.mark.integration
def test_domain_objects(domain_clock_config: BacktestConfig) -> None:
    """Create Order, Fill, Position, PortfolioState, Event without error."""
    ts_1d = list(iter_times(domain_clock_config.start, domain_clock_config.end, "1d"))
    order = Order(
        id="ord-1",
        ts=ts_1d[0],
        instrument_id="SPY|2024-03-15|C|500|100",
        side="BUY",
        qty=1,
        order_type="market",
    )
    fill = Fill(order_id=order.id, ts=ts_1d[0], fill_price=5.20, fill_qty=1)
    position = Position(
        instrument_id=order.instrument_id,
        qty=1,
        avg_price=5.20,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=100_000.0,
        positions={order.instrument_id: position},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=100_000.0,
    )
    event = Event(ts=ts_1d[0], type=EventType.FILL, payload={"order_id": order.id})
    assert order.id == "ord-1"
    assert fill.order_id == order.id
    assert position.instrument_id == order.instrument_id
    assert portfolio.equity == 100_000.0
    assert event.type == EventType.FILL
