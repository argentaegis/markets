"""Portfolio accounting tests.

Reasoning: Red-Green-Refactor per 050 plan. Tests specify apply_fill,
mark_to_market, extract_marks, assert_portfolio_invariants, settle_expirations.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.bars import BarRow
from src.domain.fill import Fill
from src.domain.order import Order
from src.domain.portfolio import PortfolioState
from src.domain.position import Position
from src.domain.quotes import Quote, QuoteStatus, Quotes
from src.domain.snapshot import MarketSnapshot

from src.domain.contract import ContractSpec
from src.portfolio.accounting import (
    apply_fill,
    assert_portfolio_invariants,
    extract_marks,
    mark_to_market,
    settle_expirations,
    settle_physical_assignment,
)


@pytest.fixture
def sample_ts() -> datetime:
    """UTC timestamp for order/fill tests."""
    return datetime(2026, 1, 15, 14, 35, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_contract_id() -> str:
    """Canonical contract_id format."""
    return "SPY|2026-03-20|C|485|100"


# --- Phase 1: apply_fill ---


def test_apply_fill_buy_opens_long_position(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Buy opens long position: cash decreases, position added."""
    portfolio = PortfolioState(
        cash=100_000.0,
        positions={},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=100_000.0,
    )
    order = Order(
        id="ord-1",
        ts=sample_ts,
        instrument_id=sample_contract_id,
        side="BUY",
        qty=2,
        order_type="market",
    )
    fill = Fill(
        order_id="ord-1",
        ts=sample_ts,
        fill_price=4.85,
        fill_qty=2,
        fees=1.0,
    )
    result = apply_fill(portfolio, fill, order, multiplier=100.0, instrument_type="option")
    # Cash: 100000 - 2*4.85*100 - 1 = 100000 - 971 = 99029
    assert result.cash == pytest.approx(99_029.0)
    assert sample_contract_id in result.positions
    pos = result.positions[sample_contract_id]
    assert pos.qty == 2
    assert pos.avg_price == 4.85
    assert pos.multiplier == 100.0
    assert pos.instrument_type == "option"
    assert result.realized_pnl == 0.0


def test_apply_fill_sell_closes_position(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Sell closes/reduces position; realized P&L on close."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=2,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=99_000.0,
        positions={sample_contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=99_000.0 + 2 * 4.85 * 100,
    )
    order = Order(
        id="ord-2",
        ts=sample_ts,
        instrument_id=sample_contract_id,
        side="SELL",
        qty=2,
        order_type="market",
    )
    fill = Fill(
        order_id="ord-2",
        ts=sample_ts,
        fill_price=5.20,
        fill_qty=2,
        fees=1.0,
    )
    result = apply_fill(portfolio, fill, order)
    # Cash: 99000 + 2*5.20*100 - 1 = 99000 + 1040 - 1 = 100039
    assert result.cash == pytest.approx(100_039.0)
    # Position closed: qty 0 or removed
    assert sample_contract_id not in result.positions or result.positions[sample_contract_id].qty == 0
    # Realized: (5.20 - 4.85) * 2 * 100 = 70
    assert result.realized_pnl == pytest.approx(70.0)


def test_apply_fill_sell_partial_close(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Sell reduces position; partial close updates qty; realized P&L on closed portion."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=3,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=98_500.0,
        positions={sample_contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=98_500.0 + 3 * 4.85 * 100,
    )
    order = Order(
        id="ord-3",
        ts=sample_ts,
        instrument_id=sample_contract_id,
        side="SELL",
        qty=1,
        order_type="market",
    )
    fill = Fill(
        order_id="ord-3",
        ts=sample_ts,
        fill_price=5.20,
        fill_qty=1,
        fees=0.5,
    )
    result = apply_fill(portfolio, fill, order)
    # Cash: 98500 + 1*5.20*100 - 0.5 = 98500 + 520 - 0.5 = 99019.5
    assert result.cash == pytest.approx(99_019.5)
    assert result.positions[sample_contract_id].qty == 2
    assert result.positions[sample_contract_id].avg_price == 4.85
    # Realized: (5.20 - 4.85) * 1 * 100 = 35
    assert result.realized_pnl == pytest.approx(35.0)


def test_apply_fill_sell_opens_short(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Sell to open creates short position (negative qty)."""
    portfolio = PortfolioState(
        cash=100_000.0,
        positions={},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=100_000.0,
    )
    order = Order(
        id="ord-4",
        ts=sample_ts,
        instrument_id=sample_contract_id,
        side="SELL",
        qty=1,
        order_type="market",
    )
    fill = Fill(
        order_id="ord-4",
        ts=sample_ts,
        fill_price=5.20,
        fill_qty=1,
        fees=1.0,
    )
    result = apply_fill(portfolio, fill, order, multiplier=100.0, instrument_type="option")
    # Short: cash increases (credit), qty negative
    assert result.cash == pytest.approx(100_000.0 + 5.20 * 100 - 1.0)
    assert result.positions[sample_contract_id].qty == -1
    assert result.positions[sample_contract_id].avg_price == 5.20


def test_apply_fill_add_to_existing_position(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Add to existing position: avg_price updates (cost basis merge)."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=2,
        avg_price=4.80,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=99_040.0,
        positions={sample_contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=99_040.0 + 2 * 4.80 * 100,
    )
    order = Order(
        id="ord-5",
        ts=sample_ts,
        instrument_id=sample_contract_id,
        side="BUY",
        qty=1,
        order_type="market",
    )
    fill = Fill(
        order_id="ord-5",
        ts=sample_ts,
        fill_price=5.00,
        fill_qty=1,
        fees=0.0,
    )
    result = apply_fill(portfolio, fill, order)
    # New avg: (2*4.80 + 1*5.00) / 3 = 4.867
    assert result.positions[sample_contract_id].qty == 3
    assert result.positions[sample_contract_id].avg_price == pytest.approx(4.867, rel=0.01)


def test_apply_fill_does_not_mutate_input(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """apply_fill returns new PortfolioState; does not mutate input."""
    portfolio = PortfolioState(
        cash=100_000.0,
        positions={},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=100_000.0,
    )
    order = Order(
        id="ord-1",
        ts=sample_ts,
        instrument_id=sample_contract_id,
        side="BUY",
        qty=1,
        order_type="market",
    )
    fill = Fill(
        order_id="ord-1",
        ts=sample_ts,
        fill_price=4.85,
        fill_qty=1,
        fees=0.0,
    )
    result = apply_fill(portfolio, fill, order)
    assert result is not portfolio
    assert portfolio.cash == 100_000.0
    assert len(portfolio.positions) == 0


# --- Phase 2: mark_to_market ---


def test_mark_to_market_updates_unrealized_and_equity(
    sample_contract_id: str,
) -> None:
    """mark_to_market computes per-position mark value; updates unrealized_pnl and equity."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=2,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    cash = 99_000.0
    portfolio = PortfolioState(
        cash=cash,
        positions={sample_contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=cash + 2 * 4.85 * 100,
    )
    marks = {sample_contract_id: 5.20}
    result = mark_to_market(portfolio, marks)
    total_mark_value = 2 * 5.20 * 100
    total_cost_basis = 2 * 4.85 * 100
    expected_unrealized = total_mark_value - total_cost_basis
    assert result.cash == cash
    assert result.positions == portfolio.positions
    assert result.realized_pnl == 0.0
    assert result.unrealized_pnl == pytest.approx(expected_unrealized)
    assert result.equity == pytest.approx(cash + total_mark_value)
    assert abs(result.equity - (result.cash + total_mark_value)) < 0.01


def test_mark_to_market_short_position(
    sample_contract_id: str,
) -> None:
    """Short position: mark value negative; unrealized = mark_value - cost_basis."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=-1,
        avg_price=5.20,
        multiplier=100.0,
        instrument_type="option",
    )
    cash = 100_520.0
    portfolio = PortfolioState(
        cash=cash,
        positions={sample_contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=cash + (-1) * 5.20 * 100,
    )
    marks = {sample_contract_id: 4.85}
    result = mark_to_market(portfolio, marks)
    mark_value = -1 * 4.85 * 100
    cost_basis = -1 * 5.20 * 100
    expected_unrealized = mark_value - cost_basis
    assert result.unrealized_pnl == pytest.approx(expected_unrealized)
    assert result.equity == pytest.approx(cash + mark_value)


def test_mark_to_market_missing_mark_uses_cost_basis(
    sample_contract_id: str,
) -> None:
    """When mark missing for a position, use cost basis (unrealized=0 for that position)."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    cash = 99_500.0
    portfolio = PortfolioState(
        cash=cash,
        positions={sample_contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=cash + 1 * 4.85 * 100,
    )
    marks: dict[str, float] = {}
    result = mark_to_market(portfolio, marks)
    assert result.unrealized_pnl == 0.0
    assert result.equity == pytest.approx(cash + 1 * 4.85 * 100)


def test_mark_to_market_realized_unchanged(
    sample_contract_id: str,
) -> None:
    """mark_to_market leaves realized_pnl unchanged."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=99_500.0,
        positions={sample_contract_id: pos},
        realized_pnl=150.0,
        unrealized_pnl=0.0,
        equity=99_500.0 + 485.0,
    )
    marks = {sample_contract_id: 5.50}
    result = mark_to_market(portfolio, marks)
    assert result.realized_pnl == 150.0


# --- Phase 3: extract_marks ---


def test_extract_marks_options_use_mid(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Options: use Quote.mid or (bid+ask)/2 per contract."""
    quote = Quote(bid=4.80, ask=4.90, mid=4.85)
    quotes = Quotes(ts=sample_ts, quotes={sample_contract_id: quote})
    snapshot = MarketSnapshot(ts=sample_ts, underlying_bar=None, option_quotes=quotes)
    result = extract_marks(snapshot, "SPY")
    assert result[sample_contract_id] == 4.85


def test_extract_marks_options_use_bid_ask_when_no_mid(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """When mid is None, use (bid+ask)/2."""
    quote = Quote(bid=4.80, ask=4.90, mid=None)
    quotes = Quotes(ts=sample_ts, quotes={sample_contract_id: quote})
    snapshot = MarketSnapshot(ts=sample_ts, underlying_bar=None, option_quotes=quotes)
    result = extract_marks(snapshot, "SPY")
    assert result[sample_contract_id] == pytest.approx(4.85)


def test_extract_marks_underlying_uses_bar_close(
    sample_ts: datetime,
) -> None:
    """Underlying: use underlying_bar.close for symbol."""
    bar = BarRow(
        ts=sample_ts,
        open=485.0,
        high=486.0,
        low=484.0,
        close=485.50,
        volume=1_000_000.0,
    )
    snapshot = MarketSnapshot(ts=sample_ts, underlying_bar=bar, option_quotes=None)
    result = extract_marks(snapshot, "SPY")
    assert result["SPY"] == 485.50


def test_extract_marks_combines_options_and_underlying(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Extract both underlying and option marks when both present."""
    bar = BarRow(
        ts=sample_ts,
        open=485.0,
        high=486.0,
        low=484.0,
        close=485.50,
        volume=1_000_000.0,
    )
    quote = Quote(bid=4.80, ask=4.90, mid=4.85)
    quotes = Quotes(ts=sample_ts, quotes={sample_contract_id: quote})
    snapshot = MarketSnapshot(
        ts=sample_ts,
        underlying_bar=bar,
        option_quotes=quotes,
    )
    result = extract_marks(snapshot, "SPY")
    assert result["SPY"] == 485.50
    assert result[sample_contract_id] == 4.85


def test_extract_marks_skips_missing_or_stale_quotes(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Skip contract_ids with QuoteStatus or None; do not include in marks."""
    quotes = Quotes(
        ts=sample_ts,
        quotes={
            sample_contract_id: QuoteStatus.MISSING,
        },
    )
    snapshot = MarketSnapshot(ts=sample_ts, underlying_bar=None, option_quotes=quotes)
    result = extract_marks(snapshot, "SPY")
    assert sample_contract_id not in result


def test_extract_marks_empty_when_no_data(
    sample_ts: datetime,
) -> None:
    """Handle None bars and None quotes gracefully; return empty or partial."""
    snapshot = MarketSnapshot(ts=sample_ts, underlying_bar=None, option_quotes=None)
    result = extract_marks(snapshot, "SPY")
    assert result == {}


# --- Phase 4: assert_portfolio_invariants ---


def test_assert_invariants_passes_valid_portfolio(
    sample_contract_id: str,
) -> None:
    """Valid portfolio: equity == cash + sum(mark_value); no NaN; int qty."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    mark_value = 5.0 * 100.0
    cash = 99_500.0
    portfolio = PortfolioState(
        cash=cash,
        positions={sample_contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=15.0,
        equity=cash + mark_value,
    )
    marks = {sample_contract_id: 5.0}
    assert_portfolio_invariants(portfolio, marks=marks)


def test_assert_invariants_raises_on_equity_mismatch(
    sample_contract_id: str,
) -> None:
    """Raises when equity != cash + sum(mark_value)."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=99_500.0,
        positions={sample_contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=100_100.0,
    )
    marks = {sample_contract_id: 5.0}
    with pytest.raises(AssertionError, match="equity"):
        assert_portfolio_invariants(portfolio, marks=marks, tolerance=0.01)


def test_assert_invariants_raises_on_nan(
    sample_contract_id: str,
) -> None:
    """Raises when cash, equity, or pnl is NaN."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=float("nan"),
        positions={sample_contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=100_000.0,
    )
    marks = {sample_contract_id: 5.0}
    with pytest.raises(AssertionError, match="NaN"):
        assert_portfolio_invariants(portfolio, marks=marks)


def test_assert_invariants_raises_on_non_int_qty(
    sample_contract_id: str,
) -> None:
    """Raises when position qty is not integer (contracts)."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=99_500.0,
        positions={sample_contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=100_000.0,
    )
    marks = {sample_contract_id: 5.0}
    assert_portfolio_invariants(portfolio, marks=marks)
    pos_bad = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    pos_bad.qty = 1.5  # type: ignore[assignment]  # invalid for options
    portfolio_bad = PortfolioState(
        cash=99_500.0,
        positions={sample_contract_id: pos_bad},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=100_000.0,
    )
    with pytest.raises(AssertionError, match="integer"):
        assert_portfolio_invariants(portfolio_bad, marks=marks)


# --- Phase 5: settle_expirations ---


def test_settle_expirations_long_receives_cash(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Long position: close at intrinsic; long receives cash."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=2,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    cash = 99_000.0
    portfolio = PortfolioState(
        cash=cash,
        positions={sample_contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=cash + 2 * 4.85 * 100,
    )
    expired = {sample_contract_id: 2.50}
    result = settle_expirations(portfolio, sample_ts, expired)
    assert sample_contract_id not in result.positions
    assert result.realized_pnl == pytest.approx((2.50 - 4.85) * 2 * 100)
    assert result.cash == pytest.approx(cash + 2 * 2.50 * 100)


def test_settle_expirations_short_pays_cash(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Short position: close at intrinsic; short pays cash."""
    pos = Position(
        instrument_id=sample_contract_id,
        qty=-1,
        avg_price=5.20,
        multiplier=100.0,
        instrument_type="option",
    )
    cash = 100_520.0
    portfolio = PortfolioState(
        cash=cash,
        positions={sample_contract_id: pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=cash + (-1) * 5.20 * 100,
    )
    expired = {sample_contract_id: 2.50}
    result = settle_expirations(portfolio, sample_ts, expired)
    assert sample_contract_id not in result.positions
    assert result.realized_pnl == pytest.approx((5.20 - 2.50) * 1 * 100)
    assert result.cash == pytest.approx(cash - 1 * 2.50 * 100)


def test_settle_expirations_skips_non_expired(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Only settle instruments in expired dict; others unchanged."""
    other_id = "SPY|2026-04-20|C|490|100"
    pos1 = Position(
        instrument_id=sample_contract_id,
        qty=1,
        avg_price=4.85,
        multiplier=100.0,
        instrument_type="option",
    )
    pos2 = Position(
        instrument_id=other_id,
        qty=1,
        avg_price=3.00,
        multiplier=100.0,
        instrument_type="option",
    )
    portfolio = PortfolioState(
        cash=99_000.0,
        positions={sample_contract_id: pos1, other_id: pos2},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=99_000.0 + 485.0 + 300.0,
    )
    expired = {sample_contract_id: 2.0}
    result = settle_expirations(portfolio, sample_ts, expired)
    assert sample_contract_id not in result.positions
    assert other_id in result.positions
    assert result.positions[other_id].qty == 1


# --- Phase 6: settle_physical_assignment (Plan 267) ---


def test_settle_physical_assignment_short_call_itm(
    sample_ts: datetime,
    sample_contract_id: str,
) -> None:
    """Short call ITM: deliver shares, receive strike; option closed; shares reduced."""
    from datetime import date

    short_call = Position(
        instrument_id=sample_contract_id,
        qty=-1,
        avg_price=5.0,
        multiplier=100.0,
        instrument_type="option",
    )
    spy_pos = Position(
        instrument_id="SPY",
        qty=100,
        avg_price=480.0,
        multiplier=1.0,
        instrument_type="equity",
    )
    cash = 50_000.0
    portfolio = PortfolioState(
        cash=cash,
        positions={sample_contract_id: short_call, "SPY": spy_pos},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=cash + 100 * 480.0 + (-1) * 5.0 * 100,
    )
    spec = ContractSpec(
        contract_id=sample_contract_id,
        underlying_symbol="SPY",
        strike=485.0,
        expiry=date(2026, 3, 20),
        right="C",
        multiplier=100.0,
    )
    intrinsic = 2.50
    result = settle_physical_assignment(portfolio, sample_contract_id, spec, intrinsic)

    assert sample_contract_id not in result.positions
    assert "SPY" not in result.positions
    assert result.cash == pytest.approx(cash + 485.0 * 100)
    share_realized = (485.0 - 480.0) * 100
    option_realized = (5.0 - 2.50) * 100
    assert result.realized_pnl == pytest.approx(share_realized + option_realized)
