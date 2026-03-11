"""Unit tests for TacticalAssetAllocationStrategy (Plan 263)."""

from datetime import datetime, timezone

from strategizer.strategies.tactical_asset_allocation import TacticalAssetAllocationStrategy
from strategizer.types import BarInput, PositionView


def _bar(ts_str: str, close: float) -> BarInput:
    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    return BarInput(ts=ts, open=close - 1, high=close + 1, low=close - 1, close=close, volume=100)


class _MockSpec:
    tick_size = 0.01
    point_value = 1.0


def _make_portfolio(equity: float = 100_000.0, positions: dict | None = None):
    class _P:
        def get_positions(self):
            return positions or {}

        def get_equity(self):
            return equity

    return _P()


def _bars_above_sma(sma_period: int = 5, close_last: float = 110) -> list[BarInput]:
    """Bars where close > SMA (close rises over period)."""
    base = 95
    return [
        _bar(f"2026-01-0{i}T21:00+00:00", base + i * 2)
        for i in range(1, sma_period + 1)
    ] + [_bar("2026-01-06T21:00+00:00", close_last)]


def _bars_below_sma(sma_period: int = 5, close_last: float = 90) -> list[BarInput]:
    """Bars where close < SMA (close falls over period)."""
    base = 105
    return [
        _bar(f"2026-01-0{i}T21:00+00:00", base - i * 2)
        for i in range(1, sma_period + 1)
    ] + [_bar("2026-01-06T21:00+00:00", close_last)]


def test_sma_filter_active() -> None:
    """Symbol with close > SMA is included in active set."""
    strat = TacticalAssetAllocationStrategy(symbols=["SPY"], sma_period=5, timeframe="1d")
    # Month change: last bar Feb 1, prev bar Jan 31
    bars = [
        _bar("2026-01-28T21:00+00:00", 97),
        _bar("2026-01-29T21:00+00:00", 98),
        _bar("2026-01-30T21:00+00:00", 99),
        _bar("2026-01-31T21:00+00:00", 100),  # prev bar
        _bar("2026-02-01T21:00+00:00", 110),  # curr: month changed, close > SMA
    ]
    portfolio = _make_portfolio(100_000.0)
    signals = strat.evaluate(
        ts=datetime(2026, 2, 1, 21, 0, tzinfo=timezone.utc),
        bars_by_symbol={"SPY": {"1d": bars}},
        specs={"SPY": _MockSpec()},
        portfolio=portfolio,
        strategy_params={"sma_period": 5, "timeframe": "1d"},
    )
    assert len(signals) >= 1
    buys = [s for s in signals if s.direction == "LONG"]
    assert len(buys) >= 1
    assert buys[0].symbol == "SPY"


def test_sma_filter_inactive() -> None:
    """Symbol with close <= SMA is excluded (sell if held)."""
    strat = TacticalAssetAllocationStrategy(symbols=["SPY"], sma_period=5, timeframe="1d")
    bars = [
        _bar("2026-01-28T21:00+00:00", 105),
        _bar("2026-01-29T21:00+00:00", 103),
        _bar("2026-01-30T21:00+00:00", 101),
        _bar("2026-01-31T21:00+00:00", 99),   # prev bar
        _bar("2026-02-01T21:00+00:00", 90),  # curr: month changed, close < SMA
    ]  # SMA ≈ 99.6, close 90 < SMA
    portfolio = _make_portfolio(100_000.0, positions={"SPY": PositionView("SPY", 100, 100.0)})
    signals = strat.evaluate(
        ts=datetime(2026, 2, 1, 21, 0, tzinfo=timezone.utc),
        bars_by_symbol={"SPY": {"1d": bars}},
        specs={"SPY": _MockSpec()},
        portfolio=portfolio,
        strategy_params={"sma_period": 5, "timeframe": "1d"},
    )
    sells = [s for s in signals if s.direction == "SHORT"]
    assert len(sells) >= 1
    assert sells[0].symbol == "SPY"
    assert sells[0].qty == 100


def test_no_trade_between_months() -> None:
    """No signals when month hasn't changed (not first bar of new month)."""
    strat = TacticalAssetAllocationStrategy(symbols=["SPY"], sma_period=5, timeframe="1d")
    bars = _bars_above_sma(sma_period=5)
    # Same month for last two bars
    portfolio = _make_portfolio(100_000.0)
    signals = strat.evaluate(
        ts=datetime(2026, 1, 6, 21, 0, tzinfo=timezone.utc),
        bars_by_symbol={"SPY": {"1d": bars}},
        specs={"SPY": _MockSpec()},
        portfolio=portfolio,
        strategy_params={"sma_period": 5, "timeframe": "1d"},
    )
    assert len(signals) == 0


def test_equal_weight_sizing() -> None:
    """When 2 symbols active, each gets ~50% of equity."""
    strat = TacticalAssetAllocationStrategy(
        symbols=["SPY", "QQQ"], sma_period=5, timeframe="1d"
    )
    spy_bars = [
        _bar("2026-01-28T21:00+00:00", 395),
        _bar("2026-01-29T21:00+00:00", 397),
        _bar("2026-01-30T21:00+00:00", 398),
        _bar("2026-01-31T21:00+00:00", 399),
        _bar("2026-02-01T21:00+00:00", 400),
    ]
    qqq_bars = [
        _bar("2026-01-28T21:00+00:00", 345),
        _bar("2026-01-29T21:00+00:00", 347),
        _bar("2026-01-30T21:00+00:00", 348),
        _bar("2026-01-31T21:00+00:00", 349),
        _bar("2026-02-01T21:00+00:00", 350),
    ]
    portfolio = _make_portfolio(100_000.0)
    signals = strat.evaluate(
        ts=datetime(2026, 2, 1, 21, 0, tzinfo=timezone.utc),
        bars_by_symbol={
            "SPY": {"1d": spy_bars},
            "QQQ": {"1d": qqq_bars},
        },
        specs={"SPY": _MockSpec(), "QQQ": _MockSpec()},
        portfolio=portfolio,
        strategy_params={"sma_period": 5, "timeframe": "1d"},
    )
    buys = [s for s in signals if s.direction == "LONG"]
    assert len(buys) == 2
    spy_qty = next(s.qty for s in buys if s.symbol == "SPY")
    qqq_qty = next(s.qty for s in buys if s.symbol == "QQQ")
    assert 100 <= spy_qty <= 150
    assert 130 <= qqq_qty <= 160


def test_all_off_sells_all() -> None:
    """When all symbols below SMA, sell entire position."""
    strat = TacticalAssetAllocationStrategy(symbols=["SPY", "QQQ"], sma_period=5, timeframe="1d")
    spy_bars = [
        _bar("2026-01-28T21:00+00:00", 105),
        _bar("2026-01-29T21:00+00:00", 103),
        _bar("2026-01-30T21:00+00:00", 101),
        _bar("2026-01-31T21:00+00:00", 99),
        _bar("2026-02-01T21:00+00:00", 90),
    ]
    qqq_bars = [
        _bar("2026-01-28T21:00+00:00", 100),
        _bar("2026-01-29T21:00+00:00", 98),
        _bar("2026-01-30T21:00+00:00", 96),
        _bar("2026-01-31T21:00+00:00", 94),
        _bar("2026-02-01T21:00+00:00", 85),
    ]
    portfolio = _make_portfolio(
        100_000.0,
        positions={
            "SPY": PositionView("SPY", 50, 200.0),
            "QQQ": PositionView("QQQ", 60, 170.0),
        },
    )
    signals = strat.evaluate(
        ts=datetime(2026, 2, 1, 21, 0, tzinfo=timezone.utc),
        bars_by_symbol={"SPY": {"1d": spy_bars}, "QQQ": {"1d": qqq_bars}},
        specs={"SPY": _MockSpec(), "QQQ": _MockSpec()},
        portfolio=portfolio,
        strategy_params={"sma_period": 5, "timeframe": "1d"},
    )
    sells = [s for s in signals if s.direction == "SHORT"]
    assert len(sells) == 2
    assert sum(1 for s in sells if s.symbol == "SPY" and s.qty == 50) == 1
    assert sum(1 for s in sells if s.symbol == "QQQ" and s.qty == 60) == 1


def test_sell_capped_at_position() -> None:
    """Rebalance-down never sells more than current position."""
    strat = TacticalAssetAllocationStrategy(symbols=["SPY"], sma_period=5, timeframe="1d")
    bars = [
        _bar("2026-01-28T21:00+00:00", 100),
        _bar("2026-01-29T21:00+00:00", 102),
        _bar("2026-01-30T21:00+00:00", 103),
        _bar("2026-01-31T21:00+00:00", 104),
        _bar("2026-02-01T21:00+00:00", 105),  # active but target < 200 (equity 50k)
    ]
    portfolio = _make_portfolio(50_000.0, positions={"SPY": PositionView("SPY", 200, 250.0)})
    signals = strat.evaluate(
        ts=datetime(2026, 2, 1, 21, 0, tzinfo=timezone.utc),
        bars_by_symbol={"SPY": {"1d": bars}},
        specs={"SPY": _MockSpec()},
        portfolio=portfolio,
        strategy_params={"sma_period": 5, "timeframe": "1d"},
    )
    sells = [s for s in signals if s.direction == "SHORT"]
    if sells:
        assert sells[0].qty <= 200
