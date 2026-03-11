"""Integration tests: portfolio accounting with DataProvider + MarketSnapshot.

Exercises extract_marks, mark_to_market, apply_fill, settle_expirations,
and assert_portfolio_invariants using real fixture data.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.fill import Fill
from src.domain.order import Order
from src.domain.portfolio import PortfolioState
from src.domain.position import Position
from src.domain.snapshot import build_market_snapshot
from src.loader.provider import LocalFileDataProvider
from src.portfolio import (
    apply_fill,
    assert_portfolio_invariants,
    extract_marks,
    mark_to_market,
    settle_expirations,
)


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def _build_snapshot(
    provider: LocalFileDataProvider,
    ts: datetime,
    contract_ids: list[str],
) -> tuple[object, object | None]:
    """Build MarketSnapshot from provider. Returns (snapshot, bar)."""
    bars = provider.get_underlying_bars("SPY", "1m", ts, ts)
    bar = bars.rows[0] if bars.rows else None
    quotes = provider.get_option_quotes(contract_ids, ts)
    return build_market_snapshot(ts, bar, quotes), bar


@pytest.mark.integration
def test_extract_marks_from_real_snapshot(provider: LocalFileDataProvider) -> None:
    """DataProvider -> MarketSnapshot -> extract_marks yields real marks."""
    ts = _utc(2026, 1, 2, 14, 35)
    contract_id = "SPY|2026-01-17|C|480|100"
    snapshot, bar = _build_snapshot(provider, ts, [contract_id])
    marks = extract_marks(snapshot, "SPY")
    assert "SPY" in marks
    assert marks["SPY"] == pytest.approx(480.8)
    assert contract_id in marks
    q = snapshot.option_quotes.quotes.get(contract_id)
    if hasattr(q, "mid") and q.mid is not None:
        assert marks[contract_id] == pytest.approx(q.mid)
    elif hasattr(q, "bid") and hasattr(q, "ask"):
        assert marks[contract_id] == pytest.approx((q.bid + q.ask) / 2, rel=0.01)


@pytest.mark.integration
def test_mark_to_market_with_real_marks(provider: LocalFileDataProvider) -> None:
    """mark_to_market with marks from real snapshot; invariants pass."""
    ts = _utc(2026, 1, 2, 14, 35)
    contract_id = "SPY|2026-01-17|C|480|100"
    snapshot, _ = _build_snapshot(provider, ts, [contract_id])
    marks = extract_marks(snapshot, "SPY")

    pos = Position(
        instrument_id=contract_id,
        qty=1,
        avg_price=5.20,
        multiplier=100.0,
        instrument_type="option",
    )
    cash = 99_480.0
    portfolio = PortfolioState(
        cash=cash,
        positions={contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=cash + 520.0,
    )
    result = mark_to_market(portfolio, marks)
    assert_portfolio_invariants(result, marks=marks)


@pytest.mark.integration
def test_apply_fill_then_mark_invariant(provider: LocalFileDataProvider) -> None:
    """apply_fill -> extract_marks -> mark_to_market -> assert invariants."""
    ts = _utc(2026, 1, 2, 14, 35)
    contract_id = "SPY|2026-01-17|C|480|100"
    snapshot, _ = _build_snapshot(provider, ts, [contract_id])
    marks = extract_marks(snapshot, "SPY")

    portfolio = PortfolioState(
        cash=100_000.0,
        positions={},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=100_000.0,
    )
    order = Order(
        id="ord-1",
        ts=ts,
        instrument_id=contract_id,
        side="BUY",
        qty=1,
        order_type="market",
    )
    fill = Fill(order_id=order.id, ts=ts, fill_price=5.30, fill_qty=1, fees=1.0)
    portfolio = apply_fill(portfolio, fill, order, multiplier=100.0, instrument_type="option")
    portfolio = mark_to_market(portfolio, marks)
    assert_portfolio_invariants(portfolio, marks=marks)
    assert contract_id in portfolio.positions
    assert portfolio.positions[contract_id].qty == 1


@pytest.mark.integration
def test_multi_step_buy_sell_cycle(provider: LocalFileDataProvider) -> None:
    """Buy -> mark -> Sell -> mark; invariants hold throughout."""
    ts = _utc(2026, 1, 2, 14, 35)
    contract_id = "SPY|2026-01-17|C|480|100"
    snapshot, _ = _build_snapshot(provider, ts, [contract_id])
    marks = extract_marks(snapshot, "SPY")

    portfolio = PortfolioState(
        cash=100_000.0,
        positions={},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=100_000.0,
    )

    order_buy = Order(
        id="ord-1",
        ts=ts,
        instrument_id=contract_id,
        side="BUY",
        qty=1,
        order_type="market",
    )
    fill_buy = Fill(order_id=order_buy.id, ts=ts, fill_price=5.30, fill_qty=1, fees=1.0)
    portfolio = apply_fill(portfolio, fill_buy, order_buy, multiplier=100.0, instrument_type="option")
    portfolio = mark_to_market(portfolio, marks)
    assert_portfolio_invariants(portfolio, marks=marks)

    order_sell = Order(
        id="ord-2",
        ts=ts,
        instrument_id=contract_id,
        side="SELL",
        qty=1,
        order_type="market",
    )
    fill_sell = Fill(order_id=order_sell.id, ts=ts, fill_price=5.50, fill_qty=1, fees=1.0)
    portfolio = apply_fill(portfolio, fill_sell, order_sell, multiplier=100.0, instrument_type="option")
    portfolio = mark_to_market(portfolio, marks)
    assert_portfolio_invariants(portfolio, marks=marks)

    assert contract_id not in portfolio.positions or portfolio.positions[contract_id].qty == 0
    assert portfolio.realized_pnl == pytest.approx((5.50 - 5.30) * 1 * 100)


@pytest.mark.integration
def test_settle_expirations_with_position(provider: LocalFileDataProvider) -> None:
    """settle_expirations closes position at intrinsic; invariants hold."""
    ts = _utc(2026, 1, 2, 14, 35)
    contract_id = "SPY|2026-01-17|C|480|100"
    pos = Position(
        instrument_id=contract_id,
        qty=1,
        avg_price=5.20,
        multiplier=100.0,
        instrument_type="option",
    )
    cash = 99_480.0
    portfolio = PortfolioState(
        cash=cash,
        positions={contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=cash + 520.0,
    )
    intrinsic = 0.80
    expired = {contract_id: intrinsic}
    result = settle_expirations(portfolio, ts, expired)
    assert contract_id not in result.positions
    assert result.realized_pnl == pytest.approx((intrinsic - 5.20) * 1 * 100)
    assert result.cash == pytest.approx(cash + 1 * intrinsic * 100)
    assert_portfolio_invariants(result, marks={})
