"""Summary metrics tests — Phase 2 of 080.

Reasoning: compute_summary derives aggregate metrics from BacktestResult.
These are written to summary.json by the reporter.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.config import BacktestConfig
from src.domain.fill import Fill
from src.domain.order import Order
from src.engine.result import BacktestResult, EquityPoint
from src.reporter.summary import SummaryMetrics, compute_summary


def _utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 2, hour, minute, tzinfo=timezone.utc)


def _make_config(**overrides) -> BacktestConfig:
    defaults = dict(
        symbol="SPY",
        start=_utc(14, 30),
        end=_utc(14, 35),
        timeframe_base="1m",
        data_provider_config={},
        initial_cash=100_000.0,
    )
    defaults.update(overrides)
    return BacktestConfig(**defaults)


def _make_result(
    equity_values: list[float] | None = None,
    orders: list[Order] | None = None,
    fills: list[Fill] | None = None,
    initial_cash: float = 100_000.0,
) -> BacktestResult:
    config = _make_config(initial_cash=initial_cash)
    curve = []
    if equity_values:
        for i, eq in enumerate(equity_values):
            curve.append(EquityPoint(ts=_utc(14, 30 + i), equity=eq))
    return BacktestResult(
        config=config,
        equity_curve=curve,
        orders=orders or [],
        fills=fills or [],
    )


def test_summary_metrics_dataclass_fields() -> None:
    """SummaryMetrics holds all required fields."""
    sm = SummaryMetrics(
        initial_cash=100_000.0,
        final_equity=100_020.0,
        total_return_pct=0.0002,
        realized_pnl=20.0,
        unrealized_pnl=0.0,
        max_drawdown=150.0,
        max_drawdown_pct=0.0015,
        num_trades=1,
        num_winning=1,
        num_losing=0,
        win_rate=1.0,
        total_fees=2.30,
        start="2026-01-02T14:30:00+00:00",
        end="2026-01-02T14:35:00+00:00",
        num_steps=5,
    )
    assert sm.num_trades == 1
    assert sm.win_rate == 1.0


def test_initial_and_final_equity() -> None:
    """compute_summary returns correct initial_cash and final_equity."""
    result = _make_result(equity_values=[100_000, 100_050, 100_020])
    sm = compute_summary(result)
    assert sm.initial_cash == 100_000.0
    assert sm.final_equity == 100_020.0


def test_total_return_pct() -> None:
    """total_return_pct = (final - initial) / initial."""
    result = _make_result(equity_values=[100_000, 101_000])
    sm = compute_summary(result)
    assert sm.total_return_pct == pytest.approx(0.01)


def test_max_drawdown_from_equity_curve() -> None:
    """max_drawdown is peak-to-trough from equity curve."""
    # Peak at 100_200, trough at 99_900 → drawdown=300
    result = _make_result(equity_values=[100_000, 100_200, 99_900, 100_050])
    sm = compute_summary(result)
    assert sm.max_drawdown == pytest.approx(300.0)


def test_max_drawdown_pct() -> None:
    """max_drawdown_pct = max_drawdown / peak."""
    result = _make_result(equity_values=[100_000, 100_200, 99_900, 100_050])
    sm = compute_summary(result)
    assert sm.max_drawdown_pct == pytest.approx(300.0 / 100_200.0)


def test_trade_counts_and_win_rate() -> None:
    """num_trades, num_winning, num_losing, win_rate computed from trades."""
    orders = [
        Order(id="b1", ts=_utc(14, 31), instrument_id="SPY|C|480", side="BUY", qty=1, order_type="market"),
        Order(id="s1", ts=_utc(14, 32), instrument_id="SPY|C|480", side="SELL", qty=1, order_type="market"),
        Order(id="b2", ts=_utc(14, 33), instrument_id="SPY|C|485", side="BUY", qty=1, order_type="market"),
        Order(id="s2", ts=_utc(14, 34), instrument_id="SPY|C|485", side="SELL", qty=1, order_type="market"),
    ]
    fills = [
        Fill(order_id="b1", ts=_utc(14, 31), fill_price=5.00, fill_qty=1),
        Fill(order_id="s1", ts=_utc(14, 32), fill_price=5.50, fill_qty=1),  # winner
        Fill(order_id="b2", ts=_utc(14, 33), fill_price=3.00, fill_qty=1),
        Fill(order_id="s2", ts=_utc(14, 34), fill_price=2.80, fill_qty=1),  # loser
    ]
    result = _make_result(
        equity_values=[100_000, 100_050, 100_100, 100_080, 100_060],
        orders=orders,
        fills=fills,
    )
    sm = compute_summary(result)
    assert sm.num_trades == 2
    assert sm.num_winning == 1
    assert sm.num_losing == 1
    assert sm.win_rate == pytest.approx(0.5)


def test_total_fees() -> None:
    """total_fees = sum of all fill fees."""
    orders = [
        Order(id="b1", ts=_utc(14, 31), instrument_id="SPY|C|480", side="BUY", qty=1, order_type="market"),
        Order(id="s1", ts=_utc(14, 32), instrument_id="SPY|C|480", side="SELL", qty=1, order_type="market"),
    ]
    fills = [
        Fill(order_id="b1", ts=_utc(14, 31), fill_price=5.00, fill_qty=1, fees=1.15),
        Fill(order_id="s1", ts=_utc(14, 32), fill_price=5.50, fill_qty=1, fees=1.15),
    ]
    result = _make_result(equity_values=[100_000, 100_020], orders=orders, fills=fills)
    sm = compute_summary(result)
    assert sm.total_fees == pytest.approx(2.30)


def test_empty_result() -> None:
    """Empty result → valid metrics with zero trades and zero drawdown."""
    result = _make_result(equity_values=[100_000])
    sm = compute_summary(result)
    assert sm.num_trades == 0
    assert sm.max_drawdown == 0.0
    assert sm.max_drawdown_pct == 0.0
    assert sm.win_rate == 0.0


def test_to_dict_json_serializable() -> None:
    """to_dict returns a JSON-serializable dict."""
    import json

    result = _make_result(equity_values=[100_000, 100_050])
    sm = compute_summary(result)
    d = sm.to_dict()
    assert isinstance(d, dict)
    json_str = json.dumps(d)
    assert "initial_cash" in json_str
