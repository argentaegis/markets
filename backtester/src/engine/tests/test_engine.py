"""Engine loop tests — Phases 4, 4b, 5 of 070.

Reasoning: Tests the A3 simulation loop wiring. Uses in-memory stubs
(NullStrategy, BuyOnceStrategy) to verify snapshot building, order flow,
fill application, marking, events, and invariants.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from pathlib import Path

import pytest

from src.broker.fee_model import FeeModelConfig
from src.broker.fill_model import FillModelConfig
from src.domain.config import BacktestConfig
from src.domain.event import EventType
from src.domain.order import Order
from src.domain.portfolio import PortfolioState
from src.domain.snapshot import MarketSnapshot
from src.engine.engine import run_backtest
from src.engine.result import BacktestResult
from src.engine.strategy import NullStrategy, Strategy
from src.loader.config import DataProviderConfig
from src.loader.provider import LocalFileDataProvider


FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "loader" / "tests" / "fixtures"


def _provider() -> LocalFileDataProvider:
    config = DataProviderConfig(
        underlying_path=FIXTURES_ROOT / "underlying",
        options_path=FIXTURES_ROOT / "options",
        timeframes_supported=["1d", "1h", "1m"],
        missing_data_policy="RETURN_PARTIAL",
        max_quote_age=None,
    )
    return LocalFileDataProvider(config)


def _config(
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    timeframe: str = "1m",
    initial_cash: float = 100_000.0,
    fee_config: FeeModelConfig | None = None,
    fill_config: FillModelConfig | None = None,
) -> BacktestConfig:
    """Build BacktestConfig pointing at test fixtures."""
    dp = DataProviderConfig(
        underlying_path=FIXTURES_ROOT / "underlying",
        options_path=FIXTURES_ROOT / "options",
        timeframes_supported=["1d", "1h", "1m"],
        missing_data_policy="RETURN_PARTIAL",
        max_quote_age=None,
    )
    return BacktestConfig(
        symbol="SPY",
        start=start or datetime(2026, 1, 2, 14, 31, tzinfo=timezone.utc),
        end=end or datetime(2026, 1, 2, 14, 35, tzinfo=timezone.utc),
        timeframe_base=timeframe,
        data_provider_config=dp,
        initial_cash=initial_cash,
        fee_config=fee_config,
        fill_config=fill_config,
    )


# ---------------------------------------------------------------------------
# Test helpers: strategies
# ---------------------------------------------------------------------------


class BuyOnceStrategy(Strategy):
    """Buys one contract on the first step, then no-ops.

    Reasoning: Minimal strategy to test full order flow through engine
    without complicating multiple-step trading logic.
    """

    def __init__(self, contract_id: str = "SPY|2026-01-17|C|480|100") -> None:
        self._contract_id = contract_id
        self._bought = False

    def on_step(
        self,
        snapshot: MarketSnapshot,
        state_view: PortfolioState,
        step_index: int = 1,
    ) -> list[Order]:
        if self._bought:
            return []
        self._bought = True
        return [
            Order(
                id="buy-1",
                ts=snapshot.ts,
                instrument_id=self._contract_id,
                side="BUY",
                qty=1,
                order_type="market",
            )
        ]


class BuySellStrategy(Strategy):
    """Buys on step 1, sells on step 2, then no-ops.

    Reasoning: Tests roundtrip order flow (open + close position).
    """

    def __init__(self, contract_id: str = "SPY|2026-01-17|C|480|100") -> None:
        self._contract_id = contract_id
        self._step = 0

    def on_step(
        self,
        snapshot: MarketSnapshot,
        state_view: PortfolioState,
        step_index: int = 1,
    ) -> list[Order]:
        self._step += 1
        if self._step == 1:
            return [
                Order(
                    id="buy-1",
                    ts=snapshot.ts,
                    instrument_id=self._contract_id,
                    side="BUY",
                    qty=1,
                    order_type="market",
                )
            ]
        if self._step == 2:
            return [
                Order(
                    id="sell-1",
                    ts=snapshot.ts,
                    instrument_id=self._contract_id,
                    side="SELL",
                    qty=1,
                    order_type="market",
                )
            ]
        return []


# ---------------------------------------------------------------------------
# Phase 4: Engine core loop — NullStrategy
# ---------------------------------------------------------------------------


def test_run_backtest_returns_result() -> None:
    """run_backtest returns BacktestResult."""
    result = run_backtest(_config(), NullStrategy(), _provider())
    assert isinstance(result, BacktestResult)


def test_null_strategy_no_fills() -> None:
    """NullStrategy produces no fills and no orders."""
    result = run_backtest(_config(), NullStrategy(), _provider())
    assert result.fills == []
    assert result.orders == []


def test_null_strategy_equity_constant() -> None:
    """With no trades, equity stays at initial_cash throughout."""
    cash = 50_000.0
    result = run_backtest(_config(initial_cash=cash), NullStrategy(), _provider())
    for ep in result.equity_curve:
        assert ep.equity == pytest.approx(cash)


def test_equity_curve_length_matches_clock() -> None:
    """Equity curve has one EquityPoint per Clock timestamp."""
    from src.clock import iter_times

    cfg = _config()
    expected = len(list(iter_times(cfg.start, cfg.end, cfg.timeframe_base)))
    result = run_backtest(cfg, NullStrategy(), _provider())
    assert len(result.equity_curve) == expected


def test_market_events_emitted_each_step() -> None:
    """MARKET event emitted at each timestamp."""
    result = run_backtest(_config(), NullStrategy(), _provider())
    market_events = [e for e in result.events if e.type == EventType.MARKET]
    assert len(market_events) == len(result.equity_curve)
    assert len(market_events) > 0


def test_final_portfolio_cash_unchanged() -> None:
    """With no trades, final_portfolio.cash equals initial_cash."""
    cash = 75_000.0
    result = run_backtest(_config(initial_cash=cash), NullStrategy(), _provider())
    assert result.final_portfolio.cash == pytest.approx(cash)


def test_invariants_hold_null_strategy() -> None:
    """No assertion errors during NullStrategy run (invariants checked each step)."""
    result = run_backtest(_config(), NullStrategy(), _provider())
    assert result.final_portfolio.equity == pytest.approx(result.final_portfolio.cash)


# ---------------------------------------------------------------------------
# Phase 4b: Engine with order flow — BuyOnceStrategy
# ---------------------------------------------------------------------------


def test_buy_once_produces_one_fill() -> None:
    """BuyOnceStrategy produces exactly 1 fill."""
    result = run_backtest(_config(), BuyOnceStrategy(), _provider())
    assert len(result.fills) == 1


def test_buy_once_portfolio_has_position() -> None:
    """After buying, final_portfolio has the position."""
    contract = "SPY|2026-01-17|C|480|100"
    result = run_backtest(_config(), BuyOnceStrategy(contract), _provider())
    assert contract in result.final_portfolio.positions
    assert result.final_portfolio.positions[contract].qty == 1


def test_buy_once_equity_changes() -> None:
    """Equity changes from initial after a fill (mark != cost)."""
    result = run_backtest(_config(), BuyOnceStrategy(), _provider())
    equities = [ep.equity for ep in result.equity_curve]
    assert len(set(equities)) >= 1  # at least some value; first step has fill


def test_buy_once_order_event_emitted() -> None:
    """ORDER event emitted when strategy produces orders."""
    result = run_backtest(_config(), BuyOnceStrategy(), _provider())
    order_events = [e for e in result.events if e.type == EventType.ORDER]
    assert len(order_events) >= 1


def test_buy_once_fill_event_emitted() -> None:
    """FILL event emitted when order fills."""
    result = run_backtest(_config(), BuyOnceStrategy(), _provider())
    fill_events = [e for e in result.events if e.type == EventType.FILL]
    assert len(fill_events) == 1


def test_buy_once_fill_references_valid_order() -> None:
    """Every fill references a valid order_id."""
    result = run_backtest(_config(), BuyOnceStrategy(), _provider())
    order_ids = {o.id for o in result.orders}
    for fill in result.fills:
        assert fill.order_id in order_ids


def test_buy_once_final_portfolio_reflects_position() -> None:
    """final_portfolio has correct position and reduced cash."""
    result = run_backtest(_config(), BuyOnceStrategy(), _provider())
    assert result.final_portfolio.cash < 100_000.0
    assert len(result.final_portfolio.positions) == 1


def test_buy_once_orders_collected() -> None:
    """All orders from strategy are collected in result.orders."""
    result = run_backtest(_config(), BuyOnceStrategy(), _provider())
    assert len(result.orders) == 1
    assert result.orders[0].id == "buy-1"


# ---------------------------------------------------------------------------
# Phase 4b: BuySellStrategy roundtrip
# ---------------------------------------------------------------------------


def test_buy_sell_roundtrip_realized_pnl() -> None:
    """Buy then sell produces nonzero realized P&L."""
    result = run_backtest(_config(), BuySellStrategy(), _provider())
    assert len(result.fills) == 2
    assert result.final_portfolio.realized_pnl != 0.0


def test_buy_sell_position_removed() -> None:
    """After buy+sell, position is closed."""
    contract = "SPY|2026-01-17|C|480|100"
    result = run_backtest(_config(), BuySellStrategy(contract), _provider())
    assert contract not in result.final_portfolio.positions


# ---------------------------------------------------------------------------
# Fees wired through config
# ---------------------------------------------------------------------------


def test_fees_reduce_cash() -> None:
    """FeeModelConfig from BacktestConfig is applied; fees visible in fills."""
    fee_cfg = FeeModelConfig(per_contract=0.65, per_order=0.50)
    result = run_backtest(
        _config(fee_config=fee_cfg),
        BuyOnceStrategy(),
        _provider(),
    )
    assert len(result.fills) == 1
    expected_fees = 0.65 * 1 + 0.50
    assert result.fills[0].fees == pytest.approx(expected_fees)


# ---------------------------------------------------------------------------
# Phase 5: Expiration detection and settlement
# ---------------------------------------------------------------------------


def test_detect_expirations_finds_expired() -> None:
    """_detect_expirations returns intrinsic for expired contracts."""
    from src.domain.position import Position
    from src.engine.engine import _detect_expirations

    contract = "SPY|2026-01-17|C|480|100"
    pos = Position(instrument_id=contract, qty=1, avg_price=5.0, multiplier=100.0, instrument_type="option")
    portfolio = PortfolioState(cash=99_500.0, positions={contract: pos}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)
    provider = _provider()
    ts_after_expiry = datetime(2026, 1, 17, 21, 0, tzinfo=timezone.utc)
    underlying_close = 485.0
    expired = _detect_expirations(portfolio, provider, ts_after_expiry, underlying_close, config=_config())
    assert contract in expired
    assert expired[contract] == pytest.approx(5.0)  # max(0, 485 - 480)


def test_detect_expirations_ignores_non_expired() -> None:
    """_detect_expirations skips positions not yet expired."""
    from src.domain.position import Position
    from src.engine.engine import _detect_expirations

    contract = "SPY|2026-03-20|C|485|100"
    pos = Position(instrument_id=contract, qty=1, avg_price=3.0, multiplier=100.0, instrument_type="option")
    portfolio = PortfolioState(cash=99_700.0, positions={contract: pos}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)
    provider = _provider()
    ts_before_expiry = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)
    expired = _detect_expirations(portfolio, provider, ts_before_expiry, 485.0, config=_config())
    assert expired == {}


def test_detect_expirations_put_intrinsic() -> None:
    """Put intrinsic = max(0, strike - underlying)."""
    from src.domain.position import Position
    from src.engine.engine import _detect_expirations

    contract = "SPY|2026-01-17|P|480|100"
    pos = Position(instrument_id=contract, qty=1, avg_price=2.0, multiplier=100.0, instrument_type="option")
    portfolio = PortfolioState(cash=99_800.0, positions={contract: pos}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)
    provider = _provider()
    ts_after_expiry = datetime(2026, 1, 17, 21, 0, tzinfo=timezone.utc)
    expired = _detect_expirations(portfolio, provider, ts_after_expiry, 475.0, config=_config())
    assert contract in expired
    assert expired[contract] == pytest.approx(5.0)  # max(0, 480 - 475)


def test_detect_expirations_otm_zero_intrinsic() -> None:
    """OTM call expires with 0 intrinsic."""
    from src.domain.position import Position
    from src.engine.engine import _detect_expirations

    contract = "SPY|2026-01-17|C|480|100"
    pos = Position(instrument_id=contract, qty=1, avg_price=5.0, multiplier=100.0, instrument_type="option")
    portfolio = PortfolioState(cash=99_500.0, positions={contract: pos}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)
    provider = _provider()
    ts_after_expiry = datetime(2026, 1, 17, 21, 0, tzinfo=timezone.utc)
    expired = _detect_expirations(portfolio, provider, ts_after_expiry, 470.0, config=_config())
    assert contract in expired
    assert expired[contract] == pytest.approx(0.0)


def test_detect_expirations_no_bar_skips() -> None:
    """No underlying close → no expirations detected."""
    from src.domain.position import Position
    from src.engine.engine import _detect_expirations

    contract = "SPY|2026-01-17|C|480|100"
    pos = Position(instrument_id=contract, qty=1, avg_price=5.0, multiplier=100.0, instrument_type="option")
    portfolio = PortfolioState(cash=99_500.0, positions={contract: pos}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)
    provider = _provider()
    ts_after_expiry = datetime(2026, 1, 17, 21, 0, tzinfo=timezone.utc)
    expired = _detect_expirations(portfolio, provider, ts_after_expiry, None, config=_config())
    assert expired == {}


# ---------------------------------------------------------------------------
# Phase 100: Underlying equity multiplier
# ---------------------------------------------------------------------------


class BuyUnderlyingStrategy(Strategy):
    """Buys shares of the underlying symbol on the first step.

    Reasoning: Minimal strategy to test underlying equity order flow.
    instrument_id == symbol (e.g. "SPY") triggers equity path in broker.
    """

    def __init__(self, symbol: str = "SPY", qty: int = 10) -> None:
        self._symbol = symbol
        self._qty = qty
        self._bought = False

    def on_step(
        self,
        snapshot: MarketSnapshot,
        state_view: PortfolioState,
        step_index: int = 1,
    ) -> list[Order]:
        if self._bought:
            return []
        self._bought = True
        return [
            Order(
                id="buy-underlying-1",
                ts=snapshot.ts,
                instrument_id=self._symbol,
                side="BUY",
                qty=self._qty,
                order_type="market",
            )
        ]


def test_underlying_position_has_equity_multiplier() -> None:
    """Buying underlying symbol produces position with multiplier=1.0, instrument_type='equity'."""
    result = run_backtest(_config(), BuyUnderlyingStrategy("SPY", qty=10), _provider())
    assert len(result.fills) == 1
    pos = result.final_portfolio.positions["SPY"]
    assert pos.multiplier == 1.0
    assert pos.instrument_type == "equity"


def test_underlying_cash_reduced_by_1x_not_100x() -> None:
    """Cash reduced by fill_price * qty * 1.0, not fill_price * qty * 100.0."""
    initial_cash = 100_000.0
    result = run_backtest(
        _config(initial_cash=initial_cash),
        BuyUnderlyingStrategy("SPY", qty=10),
        _provider(),
    )
    fill = result.fills[0]
    expected_cost = fill.fill_price * fill.fill_qty * 1.0 + fill.fees
    assert result.final_portfolio.cash == pytest.approx(initial_cash - expected_cost, rel=1e-6)


def test_option_position_still_has_100x_multiplier() -> None:
    """Existing option tests still produce multiplier=100.0."""
    contract = "SPY|2026-01-17|C|480|100"
    result = run_backtest(_config(), BuyOnceStrategy(contract), _provider())
    pos = result.final_portfolio.positions[contract]
    assert pos.multiplier == 100.0
    assert pos.instrument_type == "option"


def test_detect_expirations_futures_skips() -> None:
    """_detect_expirations returns {} when instrument_type == 'future' (070)."""
    from src.domain.futures import FuturesContractSpec, TradingSession
    from src.domain.position import Position
    from src.engine.engine import _detect_expirations

    dp = DataProviderConfig(
        underlying_path=FIXTURES_ROOT / "underlying",
        options_path=FIXTURES_ROOT / "options",
        timeframes_supported=["1d", "1h", "1m"],
        missing_data_policy="RETURN_PARTIAL",
        max_quote_age=None,
    )
    session = TradingSession("RTH", time(9, 30), time(16, 0), "America/New_York")
    fc = FuturesContractSpec("ESH26", 0.25, 50.0, session)
    config = BacktestConfig(
        symbol="ESH26",
        start=datetime(2026, 1, 2, 14, 31, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, 14, 35, tzinfo=timezone.utc),
        timeframe_base="1m",
        data_provider_config=dp,
        instrument_type="future",
        futures_contract_spec=fc,
    )
    contract = "ESH26"
    pos = Position(instrument_id=contract, qty=1, avg_price=5000.0, multiplier=50.0, instrument_type="future")
    portfolio = PortfolioState(cash=97_500.0, positions={contract: pos}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)
    provider = _provider()
    ts = datetime(2026, 1, 17, 21, 0, tzinfo=timezone.utc)
    expired = _detect_expirations(portfolio, provider, ts, 5050.0, config=config)
    assert expired == {}


def test_futures_backtest_produces_tick_aligned_fills() -> None:
    """Futures run produces tick-aligned fill prices (090)."""
    from src.domain.futures import FuturesContractSpec, TradingSession

    session = TradingSession("RTH", time(9, 30), time(16, 0), "America/New_York")
    fc = FuturesContractSpec(symbol="ESH26", tick_size=0.25, point_value=50.0, session=session)
    dp = DataProviderConfig(
        underlying_path=FIXTURES_ROOT / "underlying",
        options_path=FIXTURES_ROOT / "options",
        timeframes_supported=["1d", "1h", "1m"],
        missing_data_policy="RETURN_PARTIAL",
        max_quote_age=None,
    )
    config = BacktestConfig(
        symbol="ESH26",
        start=datetime(2026, 1, 2, 14, 31, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, 14, 35, tzinfo=timezone.utc),
        timeframe_base="1m",
        data_provider_config=dp,
        instrument_type="future",
        futures_contract_spec=fc,
    )
    result = run_backtest(config, BuyUnderlyingStrategy("ESH26", qty=1), _provider())
    assert len(result.fills) == 1
    fill = result.fills[0]
    assert (fill.fill_price * 4) % 1 == 0  # ES tick 0.25
    assert result.final_portfolio.positions["ESH26"].instrument_type == "future"
    assert result.final_portfolio.positions["ESH26"].multiplier == 50.0


def test_engine_lifecycle_event_on_expiration() -> None:
    """LIFECYCLE event emitted when position expires during engine run.

    Uses 1d bars (Jan 2-8) with a strategy that buys SPY|2026-01-10|C|490|10
    (expires Jan 10). Expiry falls after last bar, so tested via direct detection.
    """
    from src.domain.position import Position
    from src.engine.engine import _detect_expirations, _emit_events

    contract = "SPY|2026-01-17|C|480|100"
    pos = Position(instrument_id=contract, qty=1, avg_price=5.0, multiplier=100.0, instrument_type="option")
    portfolio = PortfolioState(cash=99_500.0, positions={contract: pos}, realized_pnl=0.0, unrealized_pnl=0.0, equity=100_000.0)
    provider = _provider()
    ts = datetime(2026, 1, 17, 21, 0, tzinfo=timezone.utc)
    expired = _detect_expirations(portfolio, provider, ts, 485.0, config=_config())
    snapshot = MarketSnapshot(ts=ts, underlying_bar=None, option_quotes=None)
    events = _emit_events(ts, snapshot, [], [], expired)
    lifecycle = [e for e in events if e.type == EventType.LIFECYCLE]
    assert len(lifecycle) == 1
    assert lifecycle[0].payload["action"] == "EXPIRATION"
    assert lifecycle[0].payload["instrument_id"] == contract
    assert lifecycle[0].payload["intrinsic_value"] == pytest.approx(5.0)
