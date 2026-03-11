"""Integration tests: engine loop with real DataProvider and fixtures.

Exercises full A3 simulation loop: Clock → DataProvider → Strategy →
Broker → Portfolio → events. Uses shared provider/provider_config fixtures
from conftest.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.broker.fee_model import FeeModelConfig
from src.domain.config import BacktestConfig
from src.domain.event import EventType
from src.domain.order import Order
from src.domain.portfolio import PortfolioState
from src.domain.snapshot import MarketSnapshot
from src.engine.engine import run_backtest
from src.engine.result import BacktestResult
from src.engine.strategy import NullStrategy, Strategy
from src.loader.provider import DataProviderConfig, LocalFileDataProvider


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def _engine_config(
    provider_config: DataProviderConfig,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    timeframe: str = "1m",
    initial_cash: float = 100_000.0,
    fee_config: FeeModelConfig | None = None,
) -> BacktestConfig:
    """Build BacktestConfig for engine integration tests."""
    return BacktestConfig(
        symbol="SPY",
        start=start or _utc(2026, 1, 2, 14, 31),
        end=end or _utc(2026, 1, 2, 14, 35),
        timeframe_base=timeframe,
        data_provider_config=provider_config,
        initial_cash=initial_cash,
        fee_config=fee_config,
    )


# ---------------------------------------------------------------------------
# Test helper strategies
# ---------------------------------------------------------------------------


class BuyOnceStrategy(Strategy):
    """Buys one option contract on the first step."""

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
    """Buys step 1, sells step 2."""

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
# Integration test 1: NullStrategy — no trades
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_engine_null_strategy_no_trades(
    provider_config: DataProviderConfig,
    provider: LocalFileDataProvider,
) -> None:
    """NullStrategy: no fills, no orders, equity constant, MARKET events emitted."""
    cfg = _engine_config(provider_config)
    result = run_backtest(cfg, NullStrategy(), provider)

    assert result.fills == []
    assert result.orders == []
    assert len(result.equity_curve) > 0
    for ep in result.equity_curve:
        assert ep.equity == pytest.approx(100_000.0)

    market_events = [e for e in result.events if e.type == EventType.MARKET]
    assert len(market_events) == len(result.equity_curve)


# ---------------------------------------------------------------------------
# Integration test 2: Determinism (A5)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_engine_determinism(
    provider_config: DataProviderConfig,
) -> None:
    """Same config + strategy → identical equity curves and events."""
    cfg = _engine_config(provider_config)

    p1 = LocalFileDataProvider(provider_config)
    r1 = run_backtest(cfg, NullStrategy(), p1)

    p2 = LocalFileDataProvider(provider_config)
    r2 = run_backtest(cfg, NullStrategy(), p2)

    assert len(r1.equity_curve) == len(r2.equity_curve)
    for ep1, ep2 in zip(r1.equity_curve, r2.equity_curve):
        assert ep1.ts == ep2.ts
        assert ep1.equity == pytest.approx(ep2.equity)

    assert len(r1.events) == len(r2.events)
    for e1, e2 in zip(r1.events, r2.events):
        assert e1.ts == e2.ts
        assert e1.type == e2.type


# ---------------------------------------------------------------------------
# Integration test 3: BuyOnceStrategy produces fill
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_engine_buy_once_produces_fill(
    provider_config: DataProviderConfig,
    provider: LocalFileDataProvider,
) -> None:
    """BuyOnceStrategy buys SPY|2026-01-17|C|480|100: 1 fill, position created."""
    cfg = _engine_config(provider_config)
    contract = "SPY|2026-01-17|C|480|100"
    result = run_backtest(cfg, BuyOnceStrategy(contract), provider)

    assert len(result.fills) == 1
    assert result.fills[0].fill_qty == 1
    assert contract in result.final_portfolio.positions

    order_events = [e for e in result.events if e.type == EventType.ORDER]
    fill_events = [e for e in result.events if e.type == EventType.FILL]
    assert len(order_events) >= 1
    assert len(fill_events) == 1


# ---------------------------------------------------------------------------
# Integration test 4: Buy-sell roundtrip
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_engine_buy_sell_roundtrip(
    provider_config: DataProviderConfig,
    provider: LocalFileDataProvider,
) -> None:
    """Buy step 1, sell step 2: realized P&L nonzero, position removed."""
    cfg = _engine_config(provider_config)
    contract = "SPY|2026-01-17|C|480|100"
    result = run_backtest(cfg, BuySellStrategy(contract), provider)

    assert len(result.fills) == 2
    assert contract not in result.final_portfolio.positions
    assert result.final_portfolio.realized_pnl != 0.0


# ---------------------------------------------------------------------------
# Integration test 5: Fees reduce cash
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_engine_fees_reduce_cash(
    provider_config: DataProviderConfig,
    provider: LocalFileDataProvider,
) -> None:
    """Config with FeeModelConfig applied; fees visible in fill and reduce cash."""
    fee_cfg = FeeModelConfig(per_contract=0.65, per_order=0.50)
    cfg = _engine_config(provider_config, fee_config=fee_cfg)
    result = run_backtest(cfg, BuyOnceStrategy(), provider)

    assert len(result.fills) == 1
    expected_fees = 0.65 * 1 + 0.50
    assert result.fills[0].fees == pytest.approx(expected_fees)
    assert result.final_portfolio.cash < 100_000.0


# ---------------------------------------------------------------------------
# Integration test 6: Invariants hold every step
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_engine_invariants_hold_every_step(
    provider_config: DataProviderConfig,
    provider: LocalFileDataProvider,
) -> None:
    """Multi-step run: no invariant violations, no NaN, integer qty."""
    cfg = _engine_config(provider_config)
    result = run_backtest(cfg, BuyOnceStrategy(), provider)

    for ep in result.equity_curve:
        assert ep.equity == ep.equity  # not NaN

    p = result.final_portfolio
    assert p.cash == p.cash  # not NaN
    assert p.equity == p.equity
    for pos in p.positions.values():
        assert isinstance(pos.qty, int)


# ---------------------------------------------------------------------------
# Integration test 7: Equity curve reflects marking
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_engine_equity_curve_reflects_marking(
    provider_config: DataProviderConfig,
    provider: LocalFileDataProvider,
) -> None:
    """After buying, equity curve values may differ across timestamps (marks change)."""
    cfg = _engine_config(provider_config)
    result = run_backtest(cfg, BuyOnceStrategy(), provider)

    assert len(result.equity_curve) >= 2
    equities = [ep.equity for ep in result.equity_curve]
    # First equity point should differ from initial_cash after a fill
    # (mark value of position differs from cost basis)
    assert any(e != pytest.approx(100_000.0) for e in equities)


# ---------------------------------------------------------------------------
# Integration test 8: All fills reference valid orders
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_engine_all_fills_reference_valid_orders(
    provider_config: DataProviderConfig,
    provider: LocalFileDataProvider,
) -> None:
    """000 §6 invariant: every fill references a valid order_id."""
    cfg = _engine_config(provider_config)
    result = run_backtest(cfg, BuyOnceStrategy(), provider)

    order_ids = {o.id for o in result.orders}
    for fill in result.fills:
        assert fill.order_id in order_ids
