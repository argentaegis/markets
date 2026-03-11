"""Tests for FillModel."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.order import Order
from src.domain.quotes import Quote, QuoteStatus, Quotes
from src.domain.snapshot import MarketSnapshot

# Import after we create fill_model - will add fill_order
from src.broker.fill_model import FillModelConfig, fill_order


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def _make_order(
    instrument_id: str = "SPY|2026-01-17|C|480|100",
    qty: int = 1,
    side: str = "BUY",
) -> Order:
    return Order(
        id="ord-1",
        ts=_utc(2026, 1, 2, 14, 35),
        instrument_id=instrument_id,
        side=side,
        qty=qty,
        order_type="market",
    )


@pytest.fixture
def snapshot_with_quote() -> MarketSnapshot:
    """Snapshot with bid/ask quote."""
    ts = _utc(2026, 1, 2, 14, 35)
    quotes = Quotes(
        ts=ts,
        quotes={"SPY|2026-01-17|C|480|100": Quote(bid=5.10, ask=5.30, mid=5.20)},
    )
    return MarketSnapshot(ts=ts, underlying_bar=None, option_quotes=quotes)


@pytest.fixture
def default_fill_config() -> FillModelConfig:
    return FillModelConfig(synthetic_spread_bps=50.0)


def test_fill_order_buy_fills_at_ask(snapshot_with_quote: MarketSnapshot, default_fill_config: FillModelConfig) -> None:
    """BUY order fills at ask when quotes available."""
    order = _make_order(side="BUY")
    fill = fill_order(order, snapshot_with_quote, fill_config=default_fill_config)
    assert fill is not None
    assert fill.fill_price == 5.30
    assert fill.fill_qty == 1
    assert fill.order_id == order.id
    assert fill.fees == 0.0


def test_fill_order_sell_fills_at_bid(snapshot_with_quote: MarketSnapshot, default_fill_config: FillModelConfig) -> None:
    """SELL order fills at bid when quotes available."""
    order = _make_order(side="SELL")
    fill = fill_order(order, snapshot_with_quote, fill_config=default_fill_config)
    assert fill is not None
    assert fill.fill_price == 5.10
    assert fill.fill_qty == 1


def test_fill_order_qty_matches_order(snapshot_with_quote: MarketSnapshot, default_fill_config: FillModelConfig) -> None:
    """Fill qty equals order qty for market orders."""
    order = _make_order(qty=5)
    fill = fill_order(order, snapshot_with_quote, fill_config=default_fill_config)
    assert fill is not None
    assert fill.fill_qty == 5


def test_fill_order_returns_none_when_quote_missing(default_fill_config: FillModelConfig) -> None:
    """Return None when quote is QuoteStatus or missing."""
    ts = _utc(2026, 1, 2, 14, 35)
    quotes = Quotes(ts=ts, quotes={"SPY|2026-01-17|C|480|100": QuoteStatus.MISSING})
    snapshot = MarketSnapshot(ts=ts, underlying_bar=None, option_quotes=quotes)
    order = _make_order()
    assert fill_order(order, snapshot, fill_config=default_fill_config) is None


def test_fill_order_returns_none_for_unknown_instrument(
    snapshot_with_quote: MarketSnapshot,
    default_fill_config: FillModelConfig,
) -> None:
    """Return None when instrument not in snapshot."""
    order = _make_order(instrument_id="SPY|2026-01-17|C|999|100")
    assert fill_order(order, snapshot_with_quote, fill_config=default_fill_config) is None


def test_fill_order_synthetic_spread_when_flat_quote(default_fill_config: FillModelConfig) -> None:
    """When quote has bid==ask (mid-only), use synthetic spread: BUY at mid+spread/2, SELL at mid-spread/2."""
    ts = _utc(2026, 1, 2, 14, 35)
    mid = 5.20
    quotes = Quotes(
        ts=ts,
        quotes={"SPY|2026-01-17|C|480|100": Quote(bid=mid, ask=mid, mid=mid)},
    )
    snapshot = MarketSnapshot(ts=ts, underlying_bar=None, option_quotes=quotes)

    buy_order = _make_order(side="BUY")
    buy_fill = fill_order(buy_order, snapshot, fill_config=default_fill_config)
    assert buy_fill is not None
    half_spread = mid * (default_fill_config.synthetic_spread_bps / 10000) / 2
    assert buy_fill.fill_price == pytest.approx(mid + half_spread)

    sell_order = _make_order(side="SELL")
    sell_fill = fill_order(sell_order, snapshot, fill_config=default_fill_config)
    assert sell_fill is not None
    assert sell_fill.fill_price == pytest.approx(mid - half_spread)


def test_fill_order_synthetic_spread_underlying_from_bar() -> None:
    """Underlying order uses bar close as mid with synthetic spread."""
    from src.domain.bars import BarRow

    ts = _utc(2026, 1, 2, 14, 35)
    bar = BarRow(ts=ts, open=480.0, high=481.0, low=479.0, close=480.5, volume=1000.0)
    snapshot = MarketSnapshot(ts=ts, underlying_bar=bar, option_quotes=None)
    config = FillModelConfig(synthetic_spread_bps=20.0)  # 0.2% = 0.96 on 480.5, half=0.48

    order = Order(id="ord-1", ts=ts, instrument_id="SPY", side="BUY", qty=1, order_type="market")
    fill = fill_order(order, snapshot, symbol="SPY", fill_config=config)
    assert fill is not None
    half_spread = 480.5 * 0.002 / 2
    assert fill.fill_price == pytest.approx(480.5 + half_spread)


def test_fill_order_futures_tick_aligned() -> None:
    """Futures order with futures_spec produces tick-aligned fill_price (090)."""
    from datetime import time

    from src.domain.bars import BarRow
    from src.domain.futures import FuturesContractSpec, TradingSession

    ts = _utc(2026, 1, 2, 14, 35)
    # Bar close 5412 + 50bps half-spread -> 5412 + 13.53 = 5425.53; tick-align -> 5425.50
    bar = BarRow(ts=ts, open=5410.0, high=5415.0, low=5408.0, close=5412.0, volume=50000.0)
    snapshot = MarketSnapshot(ts=ts, underlying_bar=bar, option_quotes=None)
    config = FillModelConfig(synthetic_spread_bps=50.0)
    session = TradingSession("RTH", time(9, 30), time(16, 0), "America/New_York")
    fc = FuturesContractSpec(symbol="ESH26", tick_size=0.25, point_value=50.0, session=session)

    order = Order(id="ord-1", ts=ts, instrument_id="ESH26", side="BUY", qty=1, order_type="market")
    fill = fill_order(order, snapshot, symbol="ESH26", fill_config=config, futures_spec=fc)
    assert fill is not None
    assert fill.fill_price == 5425.50  # 5425.53 rounded to nearest 0.25
    assert (fill.fill_price * 4) % 1 == 0  # ES tick 0.25 -> price * 4 is integer


def test_fill_order_options_unchanged_when_no_futures_spec(
    snapshot_with_quote: MarketSnapshot,
    default_fill_config: FillModelConfig,
) -> None:
    """Options/equity fills unchanged when futures_spec not provided."""
    order = _make_order(side="BUY")
    fill = fill_order(order, snapshot_with_quote, fill_config=default_fill_config)
    assert fill is not None
    assert fill.fill_price == 5.30  # unchanged


def test_fill_order_stop_buy_fills_when_bar_high_crosses() -> None:
    """Stop BUY at X fills when bar high >= X; fill at stop (110)."""
    from src.domain.bars import BarRow

    ts = _utc(2026, 1, 2, 14, 35)
    bar = BarRow(ts=ts, open=5398.0, high=5405.0, low=5395.0, close=5402.0, volume=1000.0)
    snapshot = MarketSnapshot(ts=ts, underlying_bar=bar, option_quotes=None)
    order = Order(
        id="ord-1",
        ts=ts,
        instrument_id="ESH26",
        side="BUY",
        qty=1,
        order_type="stop",
        limit_price=5400.0,
    )
    fill = fill_order(order, snapshot, symbol="ESH26")
    assert fill is not None
    assert fill.fill_price == 5400.0  # bar crossed stop, fill at stop


def test_fill_order_stop_sell_fills_when_bar_low_crosses() -> None:
    """Stop SELL at X fills when bar low <= X; fill at stop (110)."""
    from src.domain.bars import BarRow

    ts = _utc(2026, 1, 2, 14, 35)
    bar = BarRow(ts=ts, open=5410.0, high=5412.0, low=5398.0, close=5400.0, volume=1000.0)
    snapshot = MarketSnapshot(ts=ts, underlying_bar=bar, option_quotes=None)
    order = Order(
        id="ord-1",
        ts=ts,
        instrument_id="ESH26",
        side="SELL",
        qty=1,
        order_type="stop",
        limit_price=5400.0,
    )
    fill = fill_order(order, snapshot, symbol="ESH26")
    assert fill is not None
    assert fill.fill_price == 5400.0


def test_fill_order_stop_returns_none_when_bar_does_not_cross() -> None:
    """Stop order returns None when bar does not cross stop level."""
    from src.domain.bars import BarRow

    ts = _utc(2026, 1, 2, 14, 35)
    bar = BarRow(ts=ts, open=5395.0, high=5399.0, low=5390.0, close=5398.0, volume=1000.0)
    snapshot = MarketSnapshot(ts=ts, underlying_bar=bar, option_quotes=None)
    order = Order(
        id="ord-1",
        ts=ts,
        instrument_id="ESH26",
        side="BUY",
        qty=1,
        order_type="stop",
        limit_price=5400.0,
    )
    assert fill_order(order, snapshot, symbol="ESH26") is None
