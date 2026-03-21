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
from src.engine.result import AllocationPoint, BacktestResult, EquityPoint
from src.reporter.summary import SummaryMetrics, compute_summary


def _utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 2, hour, minute, tzinfo=timezone.utc)


def _make_config(**overrides) -> BacktestConfig:
    from src.loader.config import DataProviderConfig
    defaults = dict(
        symbol="SPY",
        start=_utc(14, 30),
        end=_utc(14, 35),
        timeframe_base="1m",
        data_provider_config=DataProviderConfig(underlying_path="", options_path=""),
        broker="zero",
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


def test_sharpe_null_when_few_observations() -> None:
    """Sharpe is null when equity curve has fewer than 20 return observations."""
    result = _make_result(equity_values=[100_000 + i * 10 for i in range(10)])  # 10 points = 9 returns
    sm = compute_summary(result)
    assert sm.sharpe is None
    assert sm.sharpe_annualization is None


def test_sharpe_computed_when_enough_observations() -> None:
    """Sharpe is computed when >= 20 return observations."""
    import math

    # 25 equity points -> 24 returns (> 20)
    base = 100_000
    eq = [base + i * 100 for i in range(25)]  # linear growth
    result = _make_result(equity_values=eq)
    sm = compute_summary(result)
    assert sm.sharpe is not None
    assert sm.sharpe_annualization == "1m/98280"
    # Constant positive returns -> high Sharpe
    assert sm.sharpe > 0


def test_cagr_null_when_sub_day() -> None:
    """CAGR is null when run spans less than 1 day."""
    config = _make_config(
        start=_utc(14, 30),
        end=_utc(14, 35),
    )
    result = BacktestResult(
        config=config,
        equity_curve=[
            EquityPoint(ts=_utc(14, 30 + i), equity=100_000 + i * 100)
            for i in range(10)
        ],
    )
    sm = compute_summary(result)
    assert sm.cagr is None


def test_cagr_computed_when_multi_day() -> None:
    """CAGR is computed when run spans at least 1 day."""
    from datetime import timedelta

    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=365)
    config = _make_config(start=start, end=end)
    result = BacktestResult(
        config=config,
        equity_curve=[
            EquityPoint(ts=start, equity=100_000),
            EquityPoint(ts=end, equity=110_000),
        ],
    )
    sm = compute_summary(result)
    assert sm.cagr is not None
    assert sm.cagr == pytest.approx(0.10, rel=0.01)


def test_turnover_computed_from_fills() -> None:
    """Turnover = sum(abs(fill_notional)) / mean(equity)."""
    orders = [
        Order(id="o1", ts=_utc(14, 31), instrument_id="SPY", side="BUY", qty=10, order_type="market"),
        Order(id="o2", ts=_utc(14, 32), instrument_id="SPY", side="SELL", qty=10, order_type="market"),
    ]
    fills = [
        Fill(order_id="o1", ts=_utc(14, 31), fill_price=400.0, fill_qty=10),
        Fill(order_id="o2", ts=_utc(14, 32), fill_price=401.0, fill_qty=10),
    ]
    eq = [100_000, 104_000, 100_100]  # mean ~101367
    result = BacktestResult(
        config=_make_config(),
        equity_curve=[EquityPoint(ts=_utc(14, 30 + i), equity=eq[i]) for i in range(3)],
        orders=orders,
        fills=fills,
        instrument_multipliers={"SPY": 1.0},
    )
    sm = compute_summary(result)
    # notional: 4000 + 4010 = 8010, mean_equity ~101367
    assert sm.turnover is not None
    assert sm.turnover == pytest.approx(8010 / 101367, rel=0.01)


def test_turnover_null_when_empty_equity() -> None:
    """Turnover is null when equity curve is empty."""
    result = BacktestResult(config=_make_config(), equity_curve=[], fills=[], orders=[])
    sm = compute_summary(result)
    assert sm.turnover is None


def _make_result_with_trades(
    winners: list[float],
    losers: list[float],
    *,
    initial_cash: float = 100_000.0,
) -> BacktestResult:
    """Build a BacktestResult with closed round-trip trades.

    winners: list of P&L values > 0 for winning trades.
    losers: list of P&L values <= 0 for losing trades.
    Each trade is a BUY then SELL on a distinct instrument to avoid FIFO ambiguity.
    """
    orders: list[Order] = []
    fills: list[Fill] = []
    hour = 14
    minute = 31

    def _ts(offset: int) -> datetime:
        return _utc(14, 30 + offset)

    step = 0
    for i, pnl in enumerate(winners + losers):
        inst = f"SPY|C|{400 + i}"
        entry_price = 5.00
        exit_price = entry_price + pnl  # qty=1, mult=1 for simplicity
        oid_b = f"b{i}"
        oid_s = f"s{i}"
        orders.append(Order(id=oid_b, ts=_ts(step), instrument_id=inst, side="BUY", qty=1, order_type="market"))
        fills.append(Fill(order_id=oid_b, ts=_ts(step), fill_price=entry_price, fill_qty=1))
        step += 1
        orders.append(Order(id=oid_s, ts=_ts(step), instrument_id=inst, side="SELL", qty=1, order_type="market"))
        fills.append(Fill(order_id=oid_s, ts=_ts(step), fill_price=exit_price, fill_qty=1))
        step += 1

    equity_values = [initial_cash + i * 10 for i in range(step + 2)]
    return BacktestResult(
        config=_make_config(initial_cash=initial_cash),
        equity_curve=[EquityPoint(ts=_ts(i), equity=eq) for i, eq in enumerate(equity_values)],
        orders=orders,
        fills=fills,
        instrument_multipliers={f"SPY|C|{400 + i}": 1.0 for i in range(len(winners) + len(losers))},
    )


def test_trade_analytics_normal_case() -> None:
    """avg_win, avg_loss, profit_factor, expectancy, reward_risk_ratio computed from mixed trades."""
    result = _make_result_with_trades(winners=[100.0, 200.0], losers=[-50.0, -150.0])
    sm = compute_summary(result)
    assert sm.avg_win == pytest.approx(150.0)
    assert sm.avg_loss == pytest.approx(-100.0)
    assert sm.profit_factor == pytest.approx(300.0 / 200.0)
    assert sm.reward_risk_ratio == pytest.approx(150.0 / 100.0)
    win_rate = 0.5
    assert sm.expectancy == pytest.approx(win_rate * 150.0 + (1 - win_rate) * (-100.0))


def test_trade_analytics_all_winners() -> None:
    """avg_loss, profit_factor, reward_risk_ratio are None when no losers."""
    result = _make_result_with_trades(winners=[100.0, 200.0], losers=[])
    sm = compute_summary(result)
    assert sm.avg_win == pytest.approx(150.0)
    assert sm.avg_loss is None
    assert sm.profit_factor is None
    assert sm.reward_risk_ratio is None
    assert sm.expectancy == pytest.approx(150.0)  # win_rate=1.0


def test_trade_analytics_all_losers() -> None:
    """avg_win, profit_factor, reward_risk_ratio are None when no winners."""
    result = _make_result_with_trades(winners=[], losers=[-80.0, -120.0])
    sm = compute_summary(result)
    assert sm.avg_win is None
    assert sm.avg_loss == pytest.approx(-100.0)
    assert sm.profit_factor is None
    assert sm.reward_risk_ratio is None
    assert sm.expectancy == pytest.approx(-100.0)  # win_rate=0.0


def test_trade_analytics_single_trade() -> None:
    """Single winning trade: avg_win set, avg_loss None."""
    result = _make_result_with_trades(winners=[300.0], losers=[])
    sm = compute_summary(result)
    assert sm.avg_win == pytest.approx(300.0)
    assert sm.avg_loss is None
    assert sm.profit_factor is None
    assert sm.expectancy == pytest.approx(300.0)


def test_trade_analytics_no_closed_trades() -> None:
    """All analytics are None when there are no closed trades."""
    result = _make_result(equity_values=[100_000])
    sm = compute_summary(result)
    assert sm.avg_win is None
    assert sm.avg_loss is None
    assert sm.profit_factor is None
    assert sm.expectancy is None
    assert sm.reward_risk_ratio is None
    assert sm.avg_trade_duration_bars is None


def test_avg_trade_duration_bars() -> None:
    """avg_trade_duration_bars is the mean bar count between entry and exit fills."""
    # Two trades: one spans 2 steps, one spans 4 steps → avg 3.0
    orders = [
        Order(id="b1", ts=_utc(14, 31), instrument_id="SPY|C|480", side="BUY", qty=1, order_type="market"),
        Order(id="s1", ts=_utc(14, 33), instrument_id="SPY|C|480", side="SELL", qty=1, order_type="market"),
        Order(id="b2", ts=_utc(14, 34), instrument_id="SPY|C|485", side="BUY", qty=1, order_type="market"),
        Order(id="s2", ts=_utc(14, 38), instrument_id="SPY|C|485", side="SELL", qty=1, order_type="market"),
    ]
    fills = [
        Fill(order_id="b1", ts=_utc(14, 31), fill_price=5.00, fill_qty=1),
        Fill(order_id="s1", ts=_utc(14, 33), fill_price=5.50, fill_qty=1),
        Fill(order_id="b2", ts=_utc(14, 34), fill_price=3.00, fill_qty=1),
        Fill(order_id="s2", ts=_utc(14, 38), fill_price=3.50, fill_qty=1),
    ]
    # equity_curve spans minutes 30..38 (9 points)
    equity_values = [100_000 + i * 10 for i in range(9)]
    result = BacktestResult(
        config=_make_config(),
        equity_curve=[EquityPoint(ts=_utc(14, 30 + i), equity=eq) for i, eq in enumerate(equity_values)],
        orders=orders,
        fills=fills,
        instrument_multipliers={"SPY|C|480": 1.0, "SPY|C|485": 1.0},
    )
    sm = compute_summary(result)
    # trade 1: entry _utc(14,31) exit _utc(14,33) → 2 min apart
    # trade 2: entry _utc(14,34) exit _utc(14,38) → 4 min apart
    # avg duration in seconds: (120 + 240) / 2 = 180s → 3.0 bars (1m timeframe → 60s per bar)
    assert sm.avg_trade_duration_bars == pytest.approx(3.0)


def test_trade_analytics_in_to_dict() -> None:
    """New analytics fields appear in to_dict() output."""
    result = _make_result_with_trades(winners=[100.0], losers=[-50.0])
    sm = compute_summary(result)
    d = sm.to_dict()
    assert "avg_win" in d
    assert "avg_loss" in d
    assert "profit_factor" in d
    assert "expectancy" in d
    assert "reward_risk_ratio" in d
    assert "avg_trade_duration_bars" in d


def test_exposure_null_when_no_allocation_curve() -> None:
    """net_exposure and gross_exposure are None when allocation_curve is empty."""
    result = _make_result(equity_values=[100_000])
    sm = compute_summary(result)
    assert sm.net_exposure is None
    assert sm.gross_exposure is None


def test_exposure_zero_when_flat_portfolio() -> None:
    """net_exposure=0.0, gross_exposure=0.0 when positions dict is empty at last step."""
    result = BacktestResult(
        config=_make_config(),
        equity_curve=[EquityPoint(ts=_utc(14, 30), equity=100_000)],
        allocation_curve=[AllocationPoint(ts=_utc(14, 30), position_values={})],
    )
    sm = compute_summary(result)
    assert sm.net_exposure == pytest.approx(0.0)
    assert sm.gross_exposure == pytest.approx(0.0)


def test_exposure_computed_from_last_allocation_point() -> None:
    """net_exposure and gross_exposure use the last AllocationPoint."""
    equity = 100_000.0
    result = BacktestResult(
        config=_make_config(),
        equity_curve=[EquityPoint(ts=_utc(14, 30 + i), equity=equity) for i in range(3)],
        allocation_curve=[
            AllocationPoint(ts=_utc(14, 30), position_values={"SPY": 50_000.0}),
            AllocationPoint(ts=_utc(14, 31), position_values={"SPY": 40_000.0}),
            AllocationPoint(ts=_utc(14, 32), position_values={"SPY": 30_000.0, "QQQ": -10_000.0}),
        ],
    )
    sm = compute_summary(result)
    # Last step: SPY=30k, QQQ=-10k → net=20k, gross=40k; equity=100k
    assert sm.net_exposure == pytest.approx(0.20)
    assert sm.gross_exposure == pytest.approx(0.40)


def test_exposure_in_to_dict() -> None:
    """net_exposure and gross_exposure appear in to_dict()."""
    equity = 100_000.0
    result = BacktestResult(
        config=_make_config(),
        equity_curve=[EquityPoint(ts=_utc(14, 30), equity=equity)],
        allocation_curve=[AllocationPoint(ts=_utc(14, 30), position_values={"SPY": 60_000.0})],
    )
    sm = compute_summary(result)
    d = sm.to_dict()
    assert "net_exposure" in d
    assert "gross_exposure" in d
    assert d["net_exposure"] == pytest.approx(0.6)
    assert d["gross_exposure"] == pytest.approx(0.6)


def test_num_open_positions() -> None:
    """num_open_positions counts trades with is_open=True."""
    # One closed trade, one open (from final_marks)
    orders = [
        Order(id="b1", ts=_utc(14, 31), instrument_id="SPY", side="BUY", qty=1, order_type="market"),
        Order(id="s1", ts=_utc(14, 32), instrument_id="SPY", side="SELL", qty=1, order_type="market"),
        Order(id="b2", ts=_utc(14, 33), instrument_id="SPY", side="BUY", qty=1, order_type="market"),
    ]
    fills = [
        Fill(order_id="b1", ts=_utc(14, 31), fill_price=400.0, fill_qty=1),
        Fill(order_id="s1", ts=_utc(14, 32), fill_price=401.0, fill_qty=1),
        Fill(order_id="b2", ts=_utc(14, 33), fill_price=402.0, fill_qty=1),
    ]
    open_marks = {"SPY": (405.0, _utc(14, 35))}
    result = BacktestResult(
        config=_make_config(),
        equity_curve=[EquityPoint(ts=_utc(14, 30 + i), equity=100_000 + i * 50) for i in range(6)],
        orders=orders,
        fills=fills,
        final_marks={"SPY": 405.0},
        instrument_multipliers={"SPY": 1.0},
    )
    sm = compute_summary(result)
    assert sm.num_trades == 1  # closed
    assert sm.num_open_positions == 1  # open at end
