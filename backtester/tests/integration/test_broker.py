"""Integration tests: Broker (validate_order, submit_orders) with DataProvider + MarketSnapshot.

Exercises FillModel, FeeModel, and order validation using real fixture data.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.order import Order
from src.domain.portfolio import PortfolioState
from src.domain.position import Position
from src.domain.snapshot import build_market_snapshot
from src.loader.provider import LocalFileDataProvider
from src.broker import FeeModelConfig, FillModelConfig, submit_orders, validate_order
from src.portfolio import apply_fill, assert_portfolio_invariants, extract_marks, mark_to_market


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


# --- Fill model (Broker/FillModel) ---


@pytest.mark.integration
def test_fillmodel_quote_based_buy_fills_at_ask(provider: LocalFileDataProvider) -> None:
    """Buy order fills at ask when quotes available."""
    ts = _utc(2026, 1, 2, 14, 35)
    contract_id = "SPY|2026-01-17|C|480|100"
    snapshot, _ = _build_snapshot(provider, ts, [contract_id])
    portfolio = PortfolioState(cash=100_000.0, positions={}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)
    order = Order(id="ord-1", ts=ts, instrument_id=contract_id, side="BUY", qty=1, order_type="market")
    fills = submit_orders([order], snapshot, portfolio, symbol="SPY")
    assert len(fills) == 1
    q = snapshot.option_quotes.quotes.get(contract_id)
    if hasattr(q, "ask") and q.ask is not None:
        assert fills[0].fill_price == pytest.approx(q.ask)
    assert fills[0].fill_qty == 1


@pytest.mark.integration
def test_fillmodel_quote_based_sell_fills_at_bid(provider: LocalFileDataProvider) -> None:
    """Sell order fills at bid when quotes available."""
    ts = _utc(2026, 1, 2, 14, 35)
    contract_id = "SPY|2026-01-17|C|480|100"
    snapshot, _ = _build_snapshot(provider, ts, [contract_id])
    pos = Position(instrument_id=contract_id, qty=1, avg_price=5.20, multiplier=100.0, instrument_type="option")
    portfolio = PortfolioState(cash=99_480.0, positions={contract_id: pos}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)
    order = Order(id="ord-1", ts=ts, instrument_id=contract_id, side="SELL", qty=1, order_type="market")
    fills = submit_orders([order], snapshot, portfolio, symbol="SPY")
    assert len(fills) == 1
    q = snapshot.option_quotes.quotes.get(contract_id)
    if hasattr(q, "bid") and q.bid is not None:
        assert fills[0].fill_price == pytest.approx(q.bid)
    assert fills[0].fill_qty == 1


@pytest.mark.integration
def test_fillmodel_synthetic_spread_when_no_quotes(provider: LocalFileDataProvider) -> None:
    """Synthetic spread used when option quotes missing - use underlying bar for underlying orders."""
    ts = _utc(2026, 1, 2, 14, 35)
    snapshot, bar = _build_snapshot(provider, ts, [])
    assert bar is not None
    portfolio = PortfolioState(cash=100_000.0, positions={}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)
    order = Order(id="ord-1", ts=ts, instrument_id="SPY", side="BUY", qty=100, order_type="market")
    fills = submit_orders([order], snapshot, portfolio, symbol="SPY")
    assert len(fills) == 1
    assert fills[0].fill_price >= bar.close
    assert fills[0].fill_qty == 100


@pytest.mark.integration
def test_fillmodel_fill_qty_matches_order(provider: LocalFileDataProvider) -> None:
    """Fill qty equals order qty for market orders."""
    ts = _utc(2026, 1, 2, 14, 35)
    contract_id = "SPY|2026-01-17|C|480|100"
    snapshot, _ = _build_snapshot(provider, ts, [contract_id])
    portfolio = PortfolioState(cash=100_000.0, positions={}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)
    order = Order(id="ord-1", ts=ts, instrument_id=contract_id, side="BUY", qty=5, order_type="market")
    fills = submit_orders([order], snapshot, portfolio, symbol="SPY")
    assert len(fills) == 1
    assert fills[0].fill_qty == 5


# --- Order validation (Broker) ---


@pytest.mark.integration
def test_order_validation_rejects_unknown_instrument(provider: LocalFileDataProvider) -> None:
    """Reject order for contract_id not in chain."""
    ts = _utc(2026, 1, 2, 14, 35)
    contract_id = "SPY|2026-01-17|C|480|100"
    snapshot, _ = _build_snapshot(provider, ts, [contract_id])
    portfolio = PortfolioState(cash=100_000.0, positions={}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)
    order = Order(
        id="ord-1",
        ts=ts,
        instrument_id="SPY|2026-01-17|C|999|100",
        side="BUY",
        qty=1,
        order_type="market",
    )
    assert validate_order(order, snapshot, portfolio, symbol="SPY") is False


@pytest.mark.integration
def test_order_validation_rejects_insufficient_buying_power(provider: LocalFileDataProvider) -> None:
    """Reject buy when cash + margin insufficient."""
    ts = _utc(2026, 1, 2, 14, 35)
    contract_id = "SPY|2026-01-17|C|480|100"
    snapshot, _ = _build_snapshot(provider, ts, [contract_id])
    portfolio = PortfolioState(cash=100.0, positions={}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100.0)
    order = Order(id="ord-1", ts=ts, instrument_id=contract_id, side="BUY", qty=100, order_type="market")
    assert validate_order(order, snapshot, portfolio, symbol="SPY") is False


@pytest.mark.integration
def test_order_validation_accepts_valid_order(provider: LocalFileDataProvider) -> None:
    """Accept valid order; produces fill."""
    ts = _utc(2026, 1, 2, 14, 35)
    contract_id = "SPY|2026-01-17|C|480|100"
    snapshot, _ = _build_snapshot(provider, ts, [contract_id])
    portfolio = PortfolioState(cash=100_000.0, positions={}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)
    order = Order(id="ord-1", ts=ts, instrument_id=contract_id, side="BUY", qty=1, order_type="market")
    fills = submit_orders([order], snapshot, portfolio, symbol="SPY")
    assert len(fills) == 1
    assert fills[0].order_id == order.id
    assert fills[0].fill_qty == 1


@pytest.mark.integration
def test_order_validation_rejects_negative_qty(provider: LocalFileDataProvider) -> None:
    """Reject order with qty <= 0."""
    ts = _utc(2026, 1, 2, 14, 35)
    contract_id = "SPY|2026-01-17|C|480|100"
    snapshot, _ = _build_snapshot(provider, ts, [contract_id])
    portfolio = PortfolioState(cash=100_000.0, positions={}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)
    for qty in (0, -1):
        order = Order(id="ord-1", ts=ts, instrument_id=contract_id, side="BUY", qty=qty, order_type="market")
        assert validate_order(order, snapshot, portfolio, symbol="SPY") is False


# --- Broker integration (extended) ---


@pytest.mark.integration
def test_broker_submit_then_apply_fill_invariant(provider: LocalFileDataProvider) -> None:
    """submit_orders -> apply_fill -> mark_to_market -> assert invariants (Broker-produced fills)."""
    ts = _utc(2026, 1, 2, 14, 35)
    contract_id = "SPY|2026-01-17|C|480|100"
    snapshot, _ = _build_snapshot(provider, ts, [contract_id])
    marks = extract_marks(snapshot, "SPY")
    portfolio = PortfolioState(cash=100_000.0, positions={}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)

    order = Order(id="ord-1", ts=ts, instrument_id=contract_id, side="BUY", qty=1, order_type="market")
    fills = submit_orders([order], snapshot, portfolio, symbol="SPY")
    assert len(fills) == 1

    order_by_id = {o.id: o for o in [order]}
    for fill in fills:
        ord_match = order_by_id[fill.order_id]
        portfolio = apply_fill(portfolio, fill, ord_match, multiplier=100.0, instrument_type="option")
    portfolio = mark_to_market(portfolio, marks)
    assert_portfolio_invariants(portfolio, marks=marks)
    assert contract_id in portfolio.positions
    assert portfolio.positions[contract_id].qty == 1


@pytest.mark.integration
def test_broker_fees_applied_and_deducted(provider: LocalFileDataProvider) -> None:
    """FeeModelConfig applied; fees reduce cash when apply_fill runs."""
    ts = _utc(2026, 1, 2, 14, 35)
    contract_id = "SPY|2026-01-17|C|480|100"
    snapshot, _ = _build_snapshot(provider, ts, [contract_id])
    initial_cash = 100_000.0
    portfolio = PortfolioState(cash=initial_cash, positions={}, realized_pnl=0.0, unrealized_pnl=0.0, equity=initial_cash)

    order = Order(id="ord-1", ts=ts, instrument_id=contract_id, side="BUY", qty=2, order_type="market")
    fee_config = FeeModelConfig(per_contract=0.65, per_order=0.50)
    fills = submit_orders([order], snapshot, portfolio, symbol="SPY", fee_config=fee_config)
    assert len(fills) == 1

    expected_fees = 0.65 * 2 + 0.50
    assert fills[0].fees == pytest.approx(expected_fees)

    portfolio = apply_fill(portfolio, fills[0], order, multiplier=100.0, instrument_type="option")
    cost = fills[0].fill_price * fills[0].fill_qty * 100.0
    assert portfolio.cash == pytest.approx(initial_cash - cost - expected_fees)


@pytest.mark.integration
def test_broker_mixed_batch_valid_and_rejected(provider: LocalFileDataProvider) -> None:
    """Mixed valid and invalid orders; only valid produces fill."""
    ts = _utc(2026, 1, 2, 14, 35)
    contract_id = "SPY|2026-01-17|C|480|100"
    snapshot, _ = _build_snapshot(provider, ts, [contract_id])
    portfolio = PortfolioState(cash=100_000.0, positions={}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)

    valid_order = Order(id="ord-1", ts=ts, instrument_id=contract_id, side="BUY", qty=1, order_type="market")
    invalid_unknown = Order(id="ord-2", ts=ts, instrument_id="SPY|2026-01-17|C|999|100", side="BUY", qty=1, order_type="market")
    invalid_negative = Order(id="ord-3", ts=ts, instrument_id=contract_id, side="BUY", qty=-1, order_type="market")

    fills = submit_orders([valid_order, invalid_unknown, invalid_negative], snapshot, portfolio, symbol="SPY")
    assert len(fills) == 1
    assert fills[0].order_id == valid_order.id


@pytest.mark.integration
def test_broker_multiple_contracts_in_batch(provider: LocalFileDataProvider) -> None:
    """Multiple contracts in one batch; each produces fill with correct price."""
    ts = _utc(2026, 1, 2, 14, 35)
    c480 = "SPY|2026-01-17|C|480|100"
    c485 = "SPY|2026-03-20|C|485|100"
    snapshot, _ = _build_snapshot(provider, ts, [c480, c485])
    portfolio = PortfolioState(cash=100_000.0, positions={}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)

    order1 = Order(id="ord-1", ts=ts, instrument_id=c480, side="BUY", qty=1, order_type="market")
    order2 = Order(id="ord-2", ts=ts, instrument_id=c485, side="BUY", qty=1, order_type="market")
    fills = submit_orders([order1, order2], snapshot, portfolio, symbol="SPY")
    assert len(fills) == 2

    order_ids = {f.order_id for f in fills}
    assert order_ids == {"ord-1", "ord-2"}

    q480 = snapshot.option_quotes.quotes.get(c480)
    q485 = snapshot.option_quotes.quotes.get(c485)
    for fill in fills:
        if fill.order_id == "ord-1" and hasattr(q480, "ask"):
            assert fill.fill_price == pytest.approx(q480.ask)
        if fill.order_id == "ord-2" and hasattr(q485, "ask"):
            assert fill.fill_price == pytest.approx(q485.ask)


@pytest.mark.integration
def test_broker_stale_quote_produces_no_fill(provider_config) -> None:
    """Stale quote (max_quote_age enforced) produces no fill."""
    from src.loader.provider import DataProviderConfig, LocalFileDataProvider

    strict_config = DataProviderConfig(
        underlying_path=provider_config.underlying_path,
        options_path=provider_config.options_path,
        timeframes_supported=provider_config.timeframes_supported,
        missing_data_policy="RETURN_PARTIAL",
        max_quote_age=60,
    )
    strict_provider = LocalFileDataProvider(strict_config)

    ts = _utc(2026, 1, 2, 14, 35)
    contract_id = "SPY|2026-01-10|C|490|10"
    snapshot, _ = _build_snapshot(strict_provider, ts, [contract_id])
    portfolio = PortfolioState(cash=100_000.0, positions={}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)

    order = Order(id="ord-1", ts=ts, instrument_id=contract_id, side="BUY", qty=1, order_type="market")
    fills = submit_orders([order], snapshot, portfolio, symbol="SPY")
    assert len(fills) == 0


@pytest.mark.integration
def test_broker_fill_order_id_in_orders(provider: LocalFileDataProvider) -> None:
    """Every fill references a valid order_id (000 §6 invariant)."""
    ts = _utc(2026, 1, 2, 14, 35)
    contract_id = "SPY|2026-01-17|C|480|100"
    snapshot, _ = _build_snapshot(provider, ts, [contract_id])
    portfolio = PortfolioState(cash=100_000.0, positions={}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)

    orders = [
        Order(id="ord-1", ts=ts, instrument_id=contract_id, side="BUY", qty=1, order_type="market"),
        Order(id="ord-2", ts=ts, instrument_id=contract_id, side="SELL", qty=1, order_type="market"),
    ]
    fills = submit_orders(orders, snapshot, portfolio, symbol="SPY")
    order_ids = {o.id for o in orders}
    assert all(f.order_id in order_ids for f in fills)


@pytest.mark.integration
def test_broker_synthetic_spread_config_affects_fill_price(provider: LocalFileDataProvider) -> None:
    """FillModelConfig.synthetic_spread_bps affects underlying fill price."""
    ts = _utc(2026, 1, 2, 14, 35)
    snapshot, bar = _build_snapshot(provider, ts, [])
    assert bar is not None
    portfolio = PortfolioState(cash=100_000.0, positions={}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)

    order = Order(id="ord-1", ts=ts, instrument_id="SPY", side="BUY", qty=1, order_type="market")
    fill_config = FillModelConfig(synthetic_spread_bps=100.0)
    fills = submit_orders([order], snapshot, portfolio, symbol="SPY", fill_config=fill_config)
    assert len(fills) == 1
    half_spread = bar.close * 0.01 / 2
    assert fills[0].fill_price == pytest.approx(bar.close + half_spread)
