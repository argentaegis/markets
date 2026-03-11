"""Backtest engine — A3 clock-driven simulation loop.

Wires Clock, DataProvider, Strategy, Broker, Portfolio into the main loop.
Each timestamp: build snapshot, call strategy, submit orders, apply fills,
mark-to-market, assert invariants, emit events, record equity.

Reasoning: Central orchestration per 000 A3. Pure function (no hidden state).
All modules communicate via domain objects only (A2).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from src.broker.broker import submit_orders
from src.broker.trailing_stop import TrailingStopManager
from src.clock.clock import count_times, iter_times
from src.domain.config import BacktestConfig
from src.domain.event import Event, EventType
from src.domain.fill import Fill
from src.domain.order import Order
from src.domain.portfolio import PortfolioState
from src.domain.snapshot import MarketSnapshot, build_market_snapshot
from src.loader.provider import DataProvider
from src.portfolio.accounting import (
    apply_fill,
    assert_portfolio_invariants,
    extract_marks,
    mark_to_market,
    settle_expirations,
)

from .result import BacktestResult, EquityPoint
from .strategy import Strategy


def _get_lookback(strategy: Strategy) -> int:
    """Get lookback (bars) from strategy.requirements(), or 500 as fallback."""
    req = getattr(strategy, "requirements", None)
    if req is None:
        return 500
    return req().lookback


def _lookback_to_timedelta(timeframe: str, lookback: int) -> timedelta:
    """Map lookback (bars) to time duration for timeframe."""
    if timeframe == "1m":
        return timedelta(minutes=lookback)
    if timeframe == "1h":
        return timedelta(hours=lookback)
    if timeframe == "1d":
        return timedelta(days=lookback)
    return timedelta(days=lookback)


def _needs_options(config: BacktestConfig | None) -> bool:
    """Whether this backtest trades options and needs chain/quote lookups."""
    if config is None:
        return True
    return config.instrument_type == "option"


def _build_step_snapshot(
    provider: DataProvider,
    symbol: str,
    timeframe: str,
    ts: datetime,
    *,
    config: BacktestConfig | None = None,
    strategy: Strategy | None = None,
) -> MarketSnapshot:
    """Build MarketSnapshot for one timestamp from DataProvider.

    Skips option chain/quote fetch for non-option instrument types (equity, future).
    For futures (instrument_type=future), fetches bar history and populates futures_bars.
    For multi-symbol equity (config.symbols non-empty), fetches current bar and history per symbol (263).
    Uses strategy lookback to narrow fetch range (Plan 153).
    """
    universe = (config.symbols or []) if config else []
    is_multi_equity = (
        config is not None
        and config.instrument_type == "equity"
        and len(universe) > 0
    )

    futures_bars: list | None = None
    bars_by_symbol: dict[str, object] | None = None
    history_by_symbol: dict[str, list] | None = None
    bar = None
    chain: list[str] = []
    quotes = None

    if config and config.instrument_type == "future":
        if strategy is not None:
            lookback = _get_lookback(strategy)
            delta = _lookback_to_timedelta(timeframe, lookback)
            effective_start = max(config.start, ts - delta)
        else:
            effective_start = config.start
        history = provider.get_underlying_bars(symbol, timeframe, effective_start, ts)
        futures_bars = list(history.rows)
        bar = futures_bars[-1] if futures_bars else None
    elif is_multi_equity:
        lookback = _get_lookback(strategy) if strategy else 210
        delta = _lookback_to_timedelta(timeframe, lookback)
        effective_start = max(config.start, ts - delta)
        bars_by_symbol = {}
        history_by_symbol = {}
        for sym in universe:
            cur = provider.get_underlying_bars(sym, timeframe, ts, ts)
            hist = provider.get_underlying_bars(sym, timeframe, effective_start, ts)
            bars_by_symbol[sym] = cur.rows[0] if cur.rows else None
            history_by_symbol[sym] = list(hist.rows)
        bar = bars_by_symbol.get(config.symbol) or (bars_by_symbol.get(universe[0]) if universe else None)
    else:
        bars = provider.get_underlying_bars(symbol, timeframe, ts, ts)
        bar = bars.rows[0] if bars.rows else None

    if _needs_options(config):
        chain = provider.get_option_chain(symbol, ts)
        quotes = provider.get_option_quotes(chain, ts) if chain else None

    return build_market_snapshot(
        ts, bar, quotes,
        futures_bars=futures_bars,
        underlying_bars_by_symbol=bars_by_symbol,
        underlying_history_by_symbol=history_by_symbol,
    )


def _instrument_params(instrument_id: str, symbol: str, config: BacktestConfig) -> tuple[float, str]:
    """Return (multiplier, instrument_type) for an instrument.

    Reasoning: equity=1.0; option=100.0; future=point_value from config.
    For futures, instrument_id == symbol (e.g. ESH26).
    For multi-symbol equity, any instrument in config.symbols is equity (263).
    """
    if config.instrument_type == "future" and config.futures_contract_spec is not None:
        return config.futures_contract_spec.point_value, "future"
    if config.instrument_type == "equity":
        universe = config.symbols or [config.symbol]
        if instrument_id in universe:
            return 1.0, "equity"
    if instrument_id == symbol:
        return 1.0, "equity"
    return 100.0, "option"


def _process_orders(
    orders: list[Order],
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
    config: BacktestConfig,
) -> tuple[PortfolioState, list[Fill]]:
    """Submit orders via Broker; apply fills to portfolio. Returns updated portfolio and fills.

    Reasoning: Separates order-flow logic from main loop for readability.
    Broker handles validation, fill model, fee model internally.
    """
    mult = None
    fc_spec = None
    if config.instrument_type == "future" and config.futures_contract_spec is not None:
        mult = config.futures_contract_spec.point_value
        fc_spec = config.futures_contract_spec
    elif config.instrument_type == "equity":
        mult = 1.0
    fills = submit_orders(
        orders,
        snapshot,
        portfolio,
        symbol=config.symbol,
        fee_config=config.fee_config,
        fill_config=config.fill_config,
        multiplier=mult,
        futures_contract_spec=fc_spec,
    )
    order_by_id = {o.id: o for o in orders}
    for fill in fills:
        matched_order = order_by_id[fill.order_id]
        multiplier, instrument_type = _instrument_params(
            matched_order.instrument_id, config.symbol, config,
        )
        portfolio = apply_fill(
            portfolio, fill, matched_order,
            multiplier=multiplier, instrument_type=instrument_type,
        )
    return portfolio, fills


def _detect_expirations(
    portfolio: PortfolioState,
    provider: DataProvider,
    ts: datetime,
    underlying_close: float | None,
    *,
    config: BacktestConfig,
) -> dict[str, float]:
    """Detect expired positions and compute intrinsic values.

    Reasoning: ContractSpec.expiry compared to ts.date(). Intrinsic value
    for calls = max(0, underlying - strike); for puts = max(0, strike - underlying).
    Returns expired dict for settle_expirations.
    Futures have no intraday expiration; skip when instrument_type == "future".
    """
    if config.instrument_type in ("future", "equity"):
        return {}
    if underlying_close is None:
        return {}
    expired: dict[str, float] = {}
    ts_date = ts.date() if hasattr(ts, "date") else ts
    for instrument_id in list(portfolio.positions.keys()):
        spec = provider.get_contract_metadata(instrument_id)
        if spec is None:
            continue
        if spec.expiry > ts_date:
            continue
        if spec.right == "C":
            intrinsic = max(0.0, underlying_close - spec.strike)
        else:
            intrinsic = max(0.0, spec.strike - underlying_close)
        expired[instrument_id] = intrinsic
    return expired


def _build_tick_size_map(config: BacktestConfig) -> dict[str, float]:
    """Build instrument_id -> tick_size for TrailingStopManager."""
    default = 0.01
    if config.instrument_type == "future" and config.futures_contract_spec:
        return {config.symbol: config.futures_contract_spec.tick_size}
    return {config.symbol: default}


def _emit_events(
    ts: datetime,
    snapshot: MarketSnapshot,
    orders: list[Order],
    fills: list[Fill],
    expired: dict[str, float],
) -> list[Event]:
    """Emit MARKET, ORDER, FILL, LIFECYCLE events for one step.

    Reasoning: Centralized event emission keeps the main loop clean.
    Events collected in list for Reporter (Step 7).
    """
    events: list[Event] = []
    events.append(Event(ts=ts, type=EventType.MARKET, payload={"symbol": "SPY"}))
    for order in orders:
        events.append(Event(
            ts=ts,
            type=EventType.ORDER,
            payload={"order_id": order.id, "instrument_id": order.instrument_id, "side": order.side, "qty": order.qty},
        ))
    for fill in fills:
        events.append(Event(
            ts=ts,
            type=EventType.FILL,
            payload={"order_id": fill.order_id, "fill_price": fill.fill_price, "fill_qty": fill.fill_qty, "fees": fill.fees},
        ))
    for instrument_id, intrinsic in expired.items():
        events.append(Event(
            ts=ts,
            type=EventType.LIFECYCLE,
            payload={"action": "EXPIRATION", "instrument_id": instrument_id, "intrinsic_value": intrinsic},
        ))
    return events


def run_backtest(
    config: BacktestConfig,
    strategy: Strategy,
    provider: DataProvider,
    on_progress: Callable[[int, int, datetime], None] | None = None,
) -> BacktestResult:
    """Execute A3 simulation loop. Returns BacktestResult with all outputs.

    Reasoning: Central orchestration function. Clock-driven iteration;
    each step builds snapshot, calls strategy, submits orders, applies fills,
    marks portfolio, detects expirations, asserts invariants, records equity.
    Deterministic given same config + strategy + data (A5).

    on_progress: Optional callback(step_index, total_steps, ts) called each step.
    """
    total_steps = count_times(config.start, config.end, config.timeframe_base)
    portfolio = PortfolioState(
        cash=config.initial_cash,
        positions={},
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        equity=config.initial_cash,
    )
    result = BacktestResult(config=config, final_portfolio=portfolio)
    marks: dict[str, float] = {}
    trailing_manager = TrailingStopManager()
    tick_size_map = _build_tick_size_map(config)

    for step_index, ts in enumerate(
        iter_times(config.start, config.end, config.timeframe_base),
        start=1,
    ):
        snapshot = _build_step_snapshot(
            provider,
            config.symbol,
            config.timeframe_base,
            ts,
            config=config,
            strategy=strategy,
        )
        orders = strategy.on_step(snapshot, portfolio, step_index=step_index)
        result.orders.extend(orders)
        portfolio, fills = _process_orders(orders, snapshot, portfolio, config)
        result.fills.extend(fills)

        order_by_id = {o.id: o for o in orders}
        for fill in fills:
            order = order_by_id.get(fill.order_id)
            if order and order.trailing_stop_ticks is not None:
                trailing_manager.register_fill(fill, order)

        trailing_fills_orders = trailing_manager.evaluate(portfolio, snapshot, tick_size_map)
        for fill, order in trailing_fills_orders:
            mult, itype = _instrument_params(order.instrument_id, config.symbol, config)
            portfolio = apply_fill(portfolio, fill, order, multiplier=mult, instrument_type=itype)
            result.orders.append(order)
            result.fills.append(fill)

        for order in orders:
            if order.instrument_id not in result.instrument_multipliers:
                mult, _ = _instrument_params(order.instrument_id, config.symbol, config)
                result.instrument_multipliers[order.instrument_id] = mult
        for fill, order in trailing_fills_orders:
            if order.instrument_id not in result.instrument_multipliers:
                mult, _ = _instrument_params(order.instrument_id, config.symbol, config)
                result.instrument_multipliers[order.instrument_id] = mult

        all_fills = list(fills) + [f for f, _ in trailing_fills_orders]
        all_orders = list(orders) + [o for _, o in trailing_fills_orders]

        marks = extract_marks(snapshot, config.symbol)
        portfolio = mark_to_market(portfolio, marks)
        bar_close = snapshot.underlying_bar.close if snapshot.underlying_bar else None
        expired = _detect_expirations(portfolio, provider, ts, bar_close, config=config)
        if expired:
            portfolio = settle_expirations(portfolio, ts, expired)
            portfolio = mark_to_market(portfolio, marks)
        assert_portfolio_invariants(portfolio, marks=marks)
        result.events.extend(_emit_events(ts, snapshot, all_orders, all_fills, expired))
        result.equity_curve.append(EquityPoint(ts=ts, equity=portfolio.equity))

        if on_progress:
            on_progress(step_index, total_steps, ts)

    result.final_portfolio = portfolio
    result.final_marks = marks
    return result
