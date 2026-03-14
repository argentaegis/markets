"""Integration tests: BuyAndHoldUnderlying — equity order flow through full pipeline.

Exercises the underlying equity path (multiplier=1.0) through engine, portfolio,
and reporter. Uses existing test fixture data (1m bars) for deterministic testing.
Phase 4 adds real-data tests against 23-month SPY daily bars.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.domain.config import BacktestConfig
from src.domain.event import EventType
from src.engine.engine import run_backtest
from src.loader.provider import DataProviderConfig, LocalFileDataProvider
from src.reporter.reporter import generate_report
from src.strategies.strategizer_adapter import StrategizerStrategy

ALL_FILES = {"equity_curve.csv", "orders.csv", "fills.csv", "trades.csv", "summary.json", "run_manifest.json", "report.html"}


def _utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 2, hour, minute, tzinfo=timezone.utc)


def _engine_config(provider_config: DataProviderConfig) -> BacktestConfig:
    return BacktestConfig(
        symbol="SPY",
        start=_utc(14, 31),
        end=_utc(14, 35),
        timeframe_base="1m",
        data_provider_config=provider_config,
        broker="zero",
        initial_cash=100_000.0,
    )


def _read_csv_rows(path: Path) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Phase 3: Fixture-based integration tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_underlying_buy_and_hold_fills(
    provider_config: DataProviderConfig,
) -> None:
    """BuyAndHoldUnderlying(symbol='SPY', qty=10): 1 fill, position has multiplier=1.0."""
    cfg = _engine_config(provider_config)
    provider = LocalFileDataProvider(provider_config)
    strategy = StrategizerStrategy("buy_and_hold_underlying", {"symbol": "SPY", "qty": 10}, config=cfg)
    result = run_backtest(cfg, strategy, provider)

    assert len(result.fills) == 1
    fill = result.fills[0]
    assert fill.fill_qty == 10
    assert fill.fill_price > 0

    pos = result.final_portfolio.positions["SPY"]
    assert pos.multiplier == 1.0
    assert pos.instrument_type == "equity"
    assert pos.qty == 10


@pytest.mark.integration
def test_underlying_equity_curve_tracks_price(
    provider_config: DataProviderConfig,
) -> None:
    """Equity curve varies as SPY price changes across steps."""
    cfg = _engine_config(provider_config)
    provider = LocalFileDataProvider(provider_config)
    strategy = StrategizerStrategy("buy_and_hold_underlying", {"symbol": "SPY", "qty": 10}, config=cfg)
    result = run_backtest(cfg, strategy, provider)

    equities = [ep.equity for ep in result.equity_curve]
    assert len(equities) >= 3
    assert len(set(equities)) > 1, "Equity should vary as SPY price moves"


@pytest.mark.integration
def test_underlying_no_expiration(
    provider_config: DataProviderConfig,
) -> None:
    """No LIFECYCLE expiration events — equities don't expire."""
    cfg = _engine_config(provider_config)
    provider = LocalFileDataProvider(provider_config)
    strategy = StrategizerStrategy("buy_and_hold_underlying", {"symbol": "SPY", "qty": 10}, config=cfg)
    result = run_backtest(cfg, strategy, provider)

    lifecycle_events = [e for e in result.events if e.type == EventType.LIFECYCLE]
    assert lifecycle_events == []


@pytest.mark.integration
def test_underlying_invariants_hold(
    provider_config: DataProviderConfig,
) -> None:
    """Portfolio invariants: equity == cash + positions, no NaN, integer qty."""
    cfg = _engine_config(provider_config)
    provider = LocalFileDataProvider(provider_config)
    strategy = StrategizerStrategy("buy_and_hold_underlying", {"symbol": "SPY", "qty": 10}, config=cfg)
    result = run_backtest(cfg, strategy, provider)

    p = result.final_portfolio
    assert p.cash == p.cash  # no NaN
    assert p.equity == p.equity
    assert p.realized_pnl == p.realized_pnl

    for pos in p.positions.values():
        assert isinstance(pos.qty, int)

    for ep in result.equity_curve:
        assert ep.equity == ep.equity  # no NaN


@pytest.mark.integration
def test_underlying_report_all_files(
    provider_config: DataProviderConfig,
    report_output_dir: Path,
) -> None:
    """generate_report produces all 6 files; trades.csv is header-only (no round-trip)."""
    cfg = _engine_config(provider_config)
    provider = LocalFileDataProvider(provider_config)
    strategy = StrategizerStrategy("buy_and_hold_underlying", {"symbol": "SPY", "qty": 10}, config=cfg)
    result = run_backtest(cfg, strategy, provider)
    run_dir = generate_report(result, report_output_dir, provider=provider)

    actual_files = {f.name for f in run_dir.iterdir()}
    assert ALL_FILES == actual_files

    trade_rows = _read_csv_rows(run_dir / "trades.csv")
    assert len(trade_rows) == 1, "Buy-and-hold open position appears as trade at mark"

    fill_rows = _read_csv_rows(run_dir / "fills.csv")
    assert len(fill_rows) == 1

    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["total_return_pct"] is not None


# ---------------------------------------------------------------------------
# Phase 4: Real-data integration test (23-month SPY 1d bars)
# ---------------------------------------------------------------------------

def _find_real_data_dir() -> Path | None:
    """Locate real SPY export data in worktree or main repo."""
    candidates = [
        Path(__file__).resolve().parents[2] / "data" / "exports" / "spy",
        Path("/Users/ajones/Code/backtester/data/exports/spy"),
    ]
    for p in candidates:
        if (p / "SPY_1d.parquet").exists():
            return p
    return None


REAL_DATA_DIR = _find_real_data_dir()
REAL_DATA_EXISTS = REAL_DATA_DIR is not None


@pytest.mark.integration
@pytest.mark.skipif(not REAL_DATA_EXISTS, reason="Real SPY data not found at data/exports/spy/SPY_1d.parquet")
def test_real_spy_buy_and_hold(
    report_output_dir: Path,
) -> None:
    """BuyAndHoldUnderlying(symbol='SPY', qty=1) over ~22 months of 1d bars.

    Verifies: fills, equity curve length, final equity > initial (SPY rose
    from ~510 to ~680 over this period), no NaN, invariants hold.
    Single share keeps the test simple and validates minimum viable trade.
    """
    assert REAL_DATA_DIR is not None  # guarded by skipif
    dp_config = DataProviderConfig(
        underlying_path=REAL_DATA_DIR,
        options_path=REAL_DATA_DIR,  # no options needed
        timeframes_supported=["1d"],
        missing_data_policy="RETURN_PARTIAL",
        max_quote_age=None,
    )
    cfg = BacktestConfig(
        symbol="SPY",
        start=datetime(2024, 3, 1, tzinfo=timezone.utc),
        end=datetime(2025, 12, 31, tzinfo=timezone.utc),
        timeframe_base="1d",
        data_provider_config=dp_config,
        broker="zero",
        initial_cash=100_000.0,
    )
    provider = LocalFileDataProvider(dp_config)
    strategy = StrategizerStrategy("buy_and_hold_underlying", {"symbol": "SPY", "qty": 1}, config=cfg)
    result = run_backtest(cfg, strategy, provider)

    # Should have many equity points (trading days)
    assert len(result.equity_curve) > 400, f"Expected 400+ equity points, got {len(result.equity_curve)}"

    # Exactly 1 fill (buy on day 1)
    assert len(result.fills) == 1

    # Final equity should exceed initial (SPY went up over this period)
    initial = cfg.initial_cash
    final = result.final_portfolio.equity
    assert final > initial, f"Expected final equity ({final}) > initial ({initial})"

    # No NaN in equity curve
    for ep in result.equity_curve:
        assert ep.equity == ep.equity, "NaN found in equity curve"

    # Position should exist with correct params
    pos = result.final_portfolio.positions["SPY"]
    assert pos.qty == 1
    assert pos.multiplier == 1.0
    assert pos.instrument_type == "equity"

    # Invariants: integer qty, no NaN in portfolio
    p = result.final_portfolio
    assert p.cash == p.cash
    assert p.equity == p.equity
    assert isinstance(pos.qty, int)

    # Generate report for inspection with --save-reports
    run_dir = generate_report(result, report_output_dir, provider=provider)
    actual_files = {f.name for f in run_dir.iterdir()}
    assert ALL_FILES == actual_files
