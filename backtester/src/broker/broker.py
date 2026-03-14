"""Broker: validate orders, submit_orders → list[Fill].

Conforms to 000 M4. Orchestrates FillModel and FeeModel.
Fee schedule keyed by instrument_type (equity, option, future).
"""

from __future__ import annotations

from collections.abc import Callable

from src.broker.fee_model import FeeModelConfig, compute_fees
from src.broker.fill_model import FillModelConfig, fill_order
from src.domain.fill import Fill
from src.domain.futures import FuturesContractSpec
from src.domain.order import Order
from src.domain.portfolio import PortfolioState
from src.domain.quotes import Quote
from src.domain.snapshot import MarketSnapshot
from src.portfolio.accounting import extract_marks


def _instrument_available(snapshot: MarketSnapshot, instrument_id: str, symbol: str) -> bool:
    """Check if instrument is available in snapshot (option or underlying).

    For multi-symbol equity (underlying_bars_by_symbol), checks that dict (263).
    """
    if snapshot.underlying_bars_by_symbol is not None:
        bar = snapshot.underlying_bars_by_symbol.get(instrument_id)
        if bar is not None:
            return True
    if snapshot.underlying_bar is not None and instrument_id == symbol:
        return True
    if snapshot.option_quotes is not None:
        q = snapshot.option_quotes.quotes.get(instrument_id)
        return isinstance(q, Quote)
    return False


def validate_order(
    order: Order,
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
    *,
    symbol: str,
    multiplier: float | None = None,
) -> bool:
    """Validate order. Returns False if rejected.

    Rejects: unknown instrument, qty <= 0, BUY when estimated cost exceeds cash.
    Uses mark-based estimate for buying power (fill price unknown until FillModel).
    When multiplier provided (e.g. futures), use it; else heuristic: equity=1, option=100.
    """
    if order.qty <= 0:
        return False
    if not _instrument_available(snapshot, order.instrument_id, symbol):
        return False
    if order.side == "BUY":
        marks = extract_marks(snapshot, symbol)
        mark = marks.get(order.instrument_id)
        if mark is None:
            return False
        mult = multiplier if multiplier is not None else (100.0 if order.instrument_id != symbol else 1.0)
        estimated_cost = mark * order.qty * mult
        if portfolio.cash < estimated_cost:
            return False
    return True


def submit_orders(
    orders: list[Order],
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
    *,
    symbol: str,
    fee_schedule: dict[str, FeeModelConfig],
    get_instrument_type: Callable[[Order], str],
    fill_config: FillModelConfig | None = None,
    multiplier: float | None = None,
    futures_contract_spec: FuturesContractSpec | None = None,
    use_open: bool = False,
) -> list[Fill]:
    """Submit orders; validate, fill, apply fees. Returns list of fills.

    fee_schedule: dict keyed by instrument_type (equity, option, future).
    get_instrument_type: callback to resolve instrument_type per order.
    When multiplier provided (e.g. instrument_type=future), used for buying power.
    When None, uses heuristic: equity=1, option=100.
    When futures_contract_spec provided, fill prices are tick-aligned (090).
    use_open: fill underlying at bar open instead of close (Plan 265 next-bar-open).
    """
    fill_cfg = fill_config or FillModelConfig()
    result: list[Fill] = []
    for order in orders:
        if not validate_order(order, snapshot, portfolio, symbol=symbol, multiplier=multiplier):
            continue
        fill = fill_order(
            order,
            snapshot,
            symbol=symbol,
            fill_config=fill_cfg,
            futures_spec=futures_contract_spec,
            use_open=use_open,
        )
        if fill is None:
            continue
        instrument_type = get_instrument_type(order)
        fee_cfg = fee_schedule.get(instrument_type) or FeeModelConfig(
            per_contract=0.0, per_order=0.0
        )
        mult_for_fee = multiplier if multiplier is not None else (
            100.0 if order.instrument_id != symbol else 1.0
        )
        fees = compute_fees(order, fill, fee_cfg, multiplier=mult_for_fee)
        result.append(
            Fill(
                order_id=fill.order_id,
                ts=fill.ts,
                fill_price=fill.fill_price,
                fill_qty=fill.fill_qty,
                fees=fees,
                liquidity_flag=fill.liquidity_flag,
            )
        )
    return result
