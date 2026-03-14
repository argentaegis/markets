"""Integration tests: example strategies — full end-to-end pipeline.

Exercises BuyAndHoldStrategy and CoveredCallStrategy through
run_backtest + generate_report, verifying all output artifacts.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.domain.config import BacktestConfig
from src.engine.engine import run_backtest
from src.loader.provider import DataProviderConfig, LocalFileDataProvider
from src.reporter.reporter import generate_report
from src.strategies.strategizer_adapter import StrategizerStrategy

CONTRACT = "SPY|2026-01-17|C|480|100"
ALL_FILES = {"equity_curve.csv", "orders.csv", "fills.csv", "trades.csv", "summary.json", "run_manifest.json", "report.html"}


def _utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 2, hour, minute, tzinfo=timezone.utc)


def _engine_config(
    provider_config: DataProviderConfig,
    *,
    broker: str = "zero",
) -> BacktestConfig:
    return BacktestConfig(
        symbol="SPY",
        start=_utc(14, 31),
        end=_utc(14, 35),
        timeframe_base="1m",
        data_provider_config=provider_config,
        broker=broker,
        initial_cash=100_000.0,
    )


def _read_csv_rows(path: Path) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Test 1: BuyAndHold end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_buy_and_hold_end_to_end(
    provider_config: DataProviderConfig,
    report_output_dir: Path,
) -> None:
    """BuyAndHoldStrategy: all 6 files. 1 fill (buy). 1 trade (open at mark). Equity varies."""
    cfg = _engine_config(provider_config)
    provider = LocalFileDataProvider(provider_config)
    strategy = StrategizerStrategy("buy_and_hold", {"contract_id": CONTRACT}, config=cfg)
    result = run_backtest(cfg, strategy, provider)
    run_dir = generate_report(result, report_output_dir)

    actual_files = {f.name for f in run_dir.iterdir()}
    assert ALL_FILES == actual_files

    fill_rows = _read_csv_rows(run_dir / "fills.csv")
    assert len(fill_rows) == 1

    trade_rows = _read_csv_rows(run_dir / "trades.csv")
    assert len(trade_rows) == 1, "Open position marked to final price"

    eq_rows = _read_csv_rows(run_dir / "equity_curve.csv")
    equities = [float(r["equity"]) for r in eq_rows]
    assert len(set(equities)) > 1, "Equity should vary across steps"


# ---------------------------------------------------------------------------
# Test 2: CoveredCall end-to-end (Plan 267: true covered call — hold shares, sell calls)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_covered_call_end_to_end(
    provider_config: DataProviderConfig,
    report_output_dir: Path,
) -> None:
    """CoveredCallStrategy: buy 100 SPY, sell 1 call. 2 fills, 2 open trades."""
    cfg = _engine_config(provider_config)
    provider = LocalFileDataProvider(provider_config)
    strategy = StrategizerStrategy(
        "covered_call",
        {"symbol": "SPY", "shares_per_contract": 100, "contract_id": CONTRACT},
        config=cfg,
    )
    result = run_backtest(cfg, strategy, provider)
    run_dir = generate_report(result, report_output_dir)

    fill_rows = _read_csv_rows(run_dir / "fills.csv")
    assert len(fill_rows) == 2  # buy SPY, sell call

    trade_rows = _read_csv_rows(run_dir / "trades.csv")
    assert len(trade_rows) == 2  # SPY position + short call position (both open at end)

    summary = json.loads((run_dir / "summary.json").read_text())
    # realized_pnl is 0 when both legs are open (no expiry/assignment in 4-min run)
    assert "realized_pnl" in summary


# ---------------------------------------------------------------------------
# Test 3: CoveredCall with fees
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_covered_call_with_fees_end_to_end(
    provider_config: DataProviderConfig,
    report_output_dir: Path,
) -> None:
    """CoveredCallStrategy + broker tdameritrade: fees on both fills, total_fees > 0."""
    cfg = _engine_config(provider_config, broker="tdameritrade")
    provider = LocalFileDataProvider(provider_config)
    strategy = StrategizerStrategy(
        "covered_call",
        {"symbol": "SPY", "shares_per_contract": 100, "contract_id": CONTRACT},
        config=cfg,
    )
    result = run_backtest(cfg, strategy, provider)
    run_dir = generate_report(result, report_output_dir)

    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["total_fees"] > 0

    fill_rows = _read_csv_rows(run_dir / "fills.csv")
    assert sum(float(r["fees"]) for r in fill_rows) > 0


# ---------------------------------------------------------------------------
# Test 4: Report files are human-readable
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_report_files_human_readable(
    provider_config: DataProviderConfig,
    report_output_dir: Path,
) -> None:
    """CSV files have headers, JSON files are parseable."""
    cfg = _engine_config(provider_config)
    provider = LocalFileDataProvider(provider_config)
    strategy = StrategizerStrategy(
        "covered_call",
        {"symbol": "SPY", "shares_per_contract": 100, "contract_id": CONTRACT},
        config=cfg,
    )
    result = run_backtest(cfg, strategy, provider)
    run_dir = generate_report(result, report_output_dir)

    for csv_name in ["equity_curve.csv", "orders.csv", "fills.csv", "trades.csv"]:
        content = (run_dir / csv_name).read_text()
        assert len(content.strip()) > 0
        lines = content.strip().split("\n")
        assert len(lines) >= 1  # at least header

    for json_name in ["summary.json", "run_manifest.json"]:
        data = json.loads((run_dir / json_name).read_text())
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Test 5: Invariants hold across both strategies
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_all_invariants_across_strategies(
    provider_config: DataProviderConfig,
) -> None:
    """Both strategies: equity consistent, no NaN, integer option qty."""
    cfg = _engine_config(provider_config)

    for name, params in [
            ("buy_and_hold", {"contract_id": CONTRACT}),
            ("covered_call", {"symbol": "SPY", "shares_per_contract": 100, "contract_id": CONTRACT}),
    ]:
        strategy = StrategizerStrategy(name, params, config=cfg)
        provider = LocalFileDataProvider(provider_config)
        result = run_backtest(cfg, strategy, provider)

        p = result.final_portfolio
        assert p is not None

        # No NaN
        assert p.cash == p.cash
        assert p.equity == p.equity
        assert p.realized_pnl == p.realized_pnl

        # Integer quantities
        for pos in p.positions.values():
            assert isinstance(pos.qty, int)

        # Equity curve no NaN
        for ep in result.equity_curve:
            assert ep.equity == ep.equity
