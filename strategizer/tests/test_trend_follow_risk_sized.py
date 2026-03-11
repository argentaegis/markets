"""Unit tests for trend_follow_risk_sized strategy (Plan 255)."""

from datetime import datetime, timezone

from strategizer.strategies.trend_follow_risk_sized import TrendFollowRiskSizedStrategy
from strategizer.types import BarInput, PositionView, Signal


def _bar(ts_str: str, close: float) -> BarInput:
    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    return BarInput(ts=ts, open=close - 1, high=close + 1, low=close - 1, close=close, volume=100)


class _MockSpec:
    tick_size = 0.25
    point_value = 50.0
    timezone = "America/New_York"
    start_time = "09:30:00"
    end_time = "16:00:00"


def _make_portfolio(cash: float = 0.0, equity: float | None = None, positions: dict | None = None):
    """Portfolio mock with configurable cash, equity, positions."""
    _equity = equity if equity is not None else cash
    _positions = positions if positions is not None else {}

    class _P:
        def get_positions(self):
            return _positions

        def get_cash(self):
            return cash

        def get_equity(self):
            return _equity

    return _P()


def _bars_long_cross(ma_period: int = 5) -> list[BarInput]:
    """Bars that trigger LONG: prev_low=97 < MA(98.4), curr_low=99 >= MA."""
    return [
        _bar("2026-01-02T14:05Z", 97),
        _bar("2026-01-02T14:10Z", 98),
        _bar("2026-01-02T14:15Z", 98),
        _bar("2026-01-02T14:20Z", 98),
        _bar("2026-01-02T14:25Z", 98),
        _bar("2026-01-02T14:30Z", 100),  # low=99 crosses above MA
    ]


def _bars_short_cross(ma_period: int = 5) -> list[BarInput]:
    """Bars that trigger SHORT: prev_high=103 > MA(101.6), curr_high=101 <= MA."""
    return [
        _bar("2026-01-02T14:05Z", 103),
        _bar("2026-01-02T14:10Z", 102),
        _bar("2026-01-02T14:15Z", 102),
        _bar("2026-01-02T14:20Z", 102),
        _bar("2026-01-02T14:25Z", 102),
        _bar("2026-01-02T14:30Z", 100),  # high=101 crosses below MA
    ]


def test_no_signal_when_already_positioned() -> None:
    """get_positions returns {symbol: pos} -> empty signal list."""
    strat = TrendFollowRiskSizedStrategy(
        symbols=["ESH26"],
        ma_period=5,
        trailing_stop_ticks=10,
        risk_pct=0.01,
        max_qty=10,
    )
    portfolio = _make_portfolio(
        cash=500_000.0,
        equity=500_000.0,
        positions={"ESH26": PositionView(instrument_id="ESH26", qty=2, avg_price=5400.0)},
    )
    signals = strat.evaluate(
        ts=datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc),
        bars_by_symbol={"ESH26": {"1m": _bars_long_cross()}},
        specs={"ESH26": _MockSpec()},
        portfolio=portfolio,
        strategy_params={"direction": "LONG", "timeframe": "1m"},
    )
    assert len(signals) == 0


def test_signal_emitted_when_flat() -> None:
    """Flat portfolio returns 1 signal with correct side."""
    strat = TrendFollowRiskSizedStrategy(
        symbols=["ESH26"],
        ma_period=5,
        trailing_stop_ticks=10,
        risk_pct=0.01,
        max_qty=10,
    )
    portfolio = _make_portfolio(cash=500_000.0, equity=500_000.0)
    signals = strat.evaluate(
        ts=datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc),
        bars_by_symbol={"ESH26": {"1m": _bars_long_cross()}},
        specs={"ESH26": _MockSpec()},
        portfolio=portfolio,
        strategy_params={"direction": "LONG", "timeframe": "1m"},
    )
    assert len(signals) == 1
    assert signals[0].direction == "LONG"
    assert signals[0].qty >= 1
    assert signals[0].trailing_stop_ticks == 10


def test_qty_scales_with_equity() -> None:
    """equity x2 -> qty x2 (within max_qty cap)."""
    strat = TrendFollowRiskSizedStrategy(
        symbols=["ESH26"],
        ma_period=5,
        trailing_stop_ticks=10,
        risk_pct=0.01,
        max_qty=100,
    )
    # risk_dollars = 0.01 * equity; stop_dollars = 10*0.25*50 = 125
    # equity 100k -> risk 1000, qty = 1000/125 = 8
    portfolio_100k = _make_portfolio(cash=200_000.0, equity=100_000.0)
    signals_100k = strat.evaluate(
        ts=datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc),
        bars_by_symbol={"ESH26": {"1m": _bars_long_cross()}},
        specs={"ESH26": _MockSpec()},
        portfolio=portfolio_100k,
        strategy_params={"direction": "LONG", "timeframe": "1m"},
    )
    # equity 200k -> risk 2000, qty = 2000/125 = 16
    portfolio_200k = _make_portfolio(cash=400_000.0, equity=200_000.0)
    signals_200k = strat.evaluate(
        ts=datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc),
        bars_by_symbol={"ESH26": {"1m": _bars_long_cross()}},
        specs={"ESH26": _MockSpec()},
        portfolio=portfolio_200k,
        strategy_params={"direction": "LONG", "timeframe": "1m"},
    )
    assert len(signals_100k) == 1 and len(signals_200k) == 1
    qty_100k = signals_100k[0].qty
    qty_200k = signals_200k[0].qty
    assert qty_200k == 2 * qty_100k


def test_max_qty_caps_oversized_accounts() -> None:
    """Very large equity -> qty == max_qty."""
    strat = TrendFollowRiskSizedStrategy(
        symbols=["ESH26"],
        ma_period=5,
        trailing_stop_ticks=10,
        risk_pct=0.01,
        max_qty=5,
    )
    portfolio = _make_portfolio(cash=10_000_000.0, equity=5_000_000.0)
    signals = strat.evaluate(
        ts=datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc),
        bars_by_symbol={"ESH26": {"1m": _bars_long_cross()}},
        specs={"ESH26": _MockSpec()},
        portfolio=portfolio,
        strategy_params={"direction": "LONG", "timeframe": "1m"},
    )
    assert len(signals) == 1
    assert signals[0].qty == 5


def test_cash_insufficient_reduces_qty() -> None:
    """get_cash too low for full qty -> reduced qty."""
    strat = TrendFollowRiskSizedStrategy(
        symbols=["ESH26"],
        ma_period=5,
        trailing_stop_ticks=10,
        risk_pct=0.01,
        max_qty=100,
    )
    # Equity 500k -> risk 5k, stop 125 -> raw qty 40, but cash limits us
    # cost_per_contract = 100 * 50 = 5000; if cash = 15000, qty = 3
    portfolio = _make_portfolio(cash=15_000.0, equity=500_000.0)
    signals = strat.evaluate(
        ts=datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc),
        bars_by_symbol={"ESH26": {"1m": _bars_long_cross()}},
        specs={"ESH26": _MockSpec()},
        portfolio=portfolio,
        strategy_params={"direction": "LONG", "timeframe": "1m"},
    )
    assert len(signals) == 1
    # 15000 / 5000 = 3 contracts
    assert signals[0].qty == 3


def test_cash_zero_suppresses_signal() -> None:
    """get_cash == 0 -> empty signal list (qty=0, not max(1,0))."""
    strat = TrendFollowRiskSizedStrategy(
        symbols=["ESH26"],
        ma_period=5,
        trailing_stop_ticks=10,
        risk_pct=0.01,
        max_qty=10,
    )
    portfolio = _make_portfolio(cash=0.0, equity=0.0)
    signals = strat.evaluate(
        ts=datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc),
        bars_by_symbol={"ESH26": {"1m": _bars_long_cross()}},
        specs={"ESH26": _MockSpec()},
        portfolio=portfolio,
        strategy_params={"direction": "LONG", "timeframe": "1m"},
    )
    assert len(signals) == 0


def test_zero_trailing_stop_ticks_no_crash() -> None:
    """trailing_stop_ticks=0 -> qty falls back to 1, no ZeroDivisionError."""
    strat = TrendFollowRiskSizedStrategy(
        symbols=["ESH26"],
        ma_period=5,
        trailing_stop_ticks=0,
        risk_pct=0.01,
        max_qty=10,
    )
    portfolio = _make_portfolio(cash=500_000.0, equity=500_000.0)
    signals = strat.evaluate(
        ts=datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc),
        bars_by_symbol={"ESH26": {"1m": _bars_long_cross()}},
        specs={"ESH26": _MockSpec()},
        portfolio=portfolio,
        strategy_params={"direction": "LONG", "timeframe": "1m"},
    )
    assert len(signals) == 1
    assert signals[0].qty == 1
    assert signals[0].trailing_stop_ticks == 0


def test_long_direction_ma_cross_fires_correctly() -> None:
    """LONG: bar low cross above MA emits signal."""
    strat = TrendFollowRiskSizedStrategy(
        symbols=["ESH26"],
        ma_period=5,
        trailing_stop_ticks=4,
        direction="LONG",
    )
    portfolio = _make_portfolio(cash=500_000.0, equity=500_000.0)
    signals = strat.evaluate(
        ts=datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc),
        bars_by_symbol={"ESH26": {"1m": _bars_long_cross()}},
        specs={"ESH26": _MockSpec()},
        portfolio=portfolio,
        strategy_params={"direction": "LONG", "timeframe": "1m"},
    )
    assert len(signals) == 1
    assert signals[0].direction == "LONG"
    assert signals[0].trailing_stop_ticks == 4


def test_short_direction_ma_cross_fires_correctly() -> None:
    """SHORT: bar high cross below MA emits signal."""
    strat = TrendFollowRiskSizedStrategy(
        symbols=["ESH26"],
        ma_period=5,
        trailing_stop_ticks=4,
        direction="SHORT",
    )
    portfolio = _make_portfolio(cash=500_000.0, equity=500_000.0)
    signals = strat.evaluate(
        ts=datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc),
        bars_by_symbol={"ESH26": {"1m": _bars_short_cross()}},
        specs={"ESH26": _MockSpec()},
        portfolio=portfolio,
        strategy_params={"direction": "SHORT", "timeframe": "1m"},
    )
    assert len(signals) == 1
    assert signals[0].direction == "SHORT"
    assert signals[0].trailing_stop_ticks == 4


def test_insufficient_bars_no_signal() -> None:
    """len(bars) < ma_period + 1 -> empty."""
    strat = TrendFollowRiskSizedStrategy(
        symbols=["ESH26"],
        ma_period=5,
        trailing_stop_ticks=10,
    )
    portfolio = _make_portfolio(cash=500_000.0, equity=500_000.0)
    bars = _bars_long_cross()[:4]  # only 4 bars, need 6
    signals = strat.evaluate(
        ts=datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc),
        bars_by_symbol={"ESH26": {"1m": bars}},
        specs={"ESH26": _MockSpec()},
        portfolio=portfolio,
        strategy_params={"direction": "LONG", "timeframe": "1m"},
    )
    assert len(signals) == 0


def test_trailing_stop_ticks_passed_through() -> None:
    """Signal has correct trailing_stop_ticks."""
    strat = TrendFollowRiskSizedStrategy(
        symbols=["ESH26"],
        ma_period=5,
        trailing_stop_ticks=17,
    )
    portfolio = _make_portfolio(cash=500_000.0, equity=500_000.0)
    signals = strat.evaluate(
        ts=datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc),
        bars_by_symbol={"ESH26": {"1m": _bars_long_cross()}},
        specs={"ESH26": _MockSpec()},
        portfolio=portfolio,
        strategy_params={"direction": "LONG", "trailing_stop_ticks": 17, "timeframe": "1m"},
    )
    assert len(signals) == 1
    assert signals[0].trailing_stop_ticks == 17
