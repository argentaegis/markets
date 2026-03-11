"""Integration tests: Reporter — full pipeline from run_backtest → generate_report → verify artifacts.

Exercises end-to-end: engine produces BacktestResult, reporter writes all 6 files.
Uses shared provider/provider_config fixtures from conftest.py.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.broker.fee_model import FeeModelConfig
from src.domain.config import BacktestConfig
from src.domain.order import Order
from src.domain.portfolio import PortfolioState
from src.domain.snapshot import MarketSnapshot
from src.engine.engine import run_backtest
from src.engine.result import BacktestResult
from src.engine.strategy import NullStrategy, Strategy
from src.loader.provider import DataProviderConfig, LocalFileDataProvider
from src.reporter.reporter import generate_report


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
    """Build BacktestConfig for reporter integration tests."""
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
# Shared strategies (same as engine integration tests)
# ---------------------------------------------------------------------------


class BuyOnceStrategy(Strategy):
    """Buys one option contract on the first step."""

    def __init__(self, contract_id: str = "SPY|2026-01-17|C|480|100") -> None:
        self._contract_id = contract_id
        self._bought = False

    def on_step(self, snapshot: MarketSnapshot, state_view: PortfolioState, step_index: int = 1) -> list[Order]:
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

    def on_step(self, snapshot: MarketSnapshot, state_view: PortfolioState, step_index: int = 1) -> list[Order]:
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
# Helper: read CSV rows from file
# ---------------------------------------------------------------------------


def _read_csv(path: Path) -> tuple[list[str], list[dict]]:
    """Read CSV, return (fieldnames, rows)."""
    with open(path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


ALL_FILES = {"equity_curve.csv", "orders.csv", "fills.csv", "trades.csv", "summary.json", "run_manifest.json", "report.html"}


# ---------------------------------------------------------------------------
# Test 1: NullStrategy — all files exist
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_report_null_strategy_all_files(
    provider_config: DataProviderConfig,
    provider: LocalFileDataProvider,
    report_output_dir: Path,
) -> None:
    """NullStrategy run → generate_report. All 6 files exist. equity_curve has rows.
    orders/fills are header-only. summary.json parseable."""
    cfg = _engine_config(provider_config)
    result = run_backtest(cfg, NullStrategy(), provider)
    run_dir = generate_report(result, report_output_dir)

    actual_files = {f.name for f in run_dir.iterdir()}
    assert ALL_FILES == actual_files

    _, eq_rows = _read_csv(run_dir / "equity_curve.csv")
    assert len(eq_rows) > 0

    _, order_rows = _read_csv(run_dir / "orders.csv")
    assert len(order_rows) == 0

    _, fill_rows = _read_csv(run_dir / "fills.csv")
    assert len(fill_rows) == 0

    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["num_trades"] == 0


# ---------------------------------------------------------------------------
# Test 2: BuyOnce — trades.csv empty (position still open)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_report_buy_once_trades_csv(
    provider_config: DataProviderConfig,
    provider: LocalFileDataProvider,
    report_output_dir: Path,
) -> None:
    """BuyOnceStrategy: trades.csv has 1 row (open position marked to final price).
    fills.csv has 1 row. orders.csv has 1 row."""
    cfg = _engine_config(provider_config)
    result = run_backtest(cfg, BuyOnceStrategy(), provider)
    run_dir = generate_report(result, report_output_dir)

    _, trade_rows = _read_csv(run_dir / "trades.csv")
    assert len(trade_rows) == 1, "Open position marked to final price"

    _, fill_rows = _read_csv(run_dir / "fills.csv")
    assert len(fill_rows) == 1

    _, order_rows = _read_csv(run_dir / "orders.csv")
    assert len(order_rows) == 1


# ---------------------------------------------------------------------------
# Test 3: BuySell — round-trip trade in trades.csv
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_report_buy_sell_roundtrip_trade(
    provider_config: DataProviderConfig,
    provider: LocalFileDataProvider,
    report_output_dir: Path,
) -> None:
    """BuySellStrategy: trades.csv has 1 trade with entry/exit prices and realized P&L."""
    cfg = _engine_config(provider_config)
    result = run_backtest(cfg, BuySellStrategy(), provider)
    run_dir = generate_report(result, report_output_dir)

    _, trade_rows = _read_csv(run_dir / "trades.csv")
    assert len(trade_rows) == 1
    trade = trade_rows[0]
    assert trade["side"] == "LONG"
    assert float(trade["entry_price"]) > 0
    assert float(trade["exit_price"]) > 0
    assert "realized_pnl" in trade


# ---------------------------------------------------------------------------
# Test 4: Summary metrics consistent
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_report_summary_metrics_consistent(
    provider_config: DataProviderConfig,
    provider: LocalFileDataProvider,
    report_output_dir: Path,
) -> None:
    """Summary total_return_pct matches equity. max_drawdown >= 0.
    num_trades matches trades.csv row count."""
    cfg = _engine_config(provider_config)
    result = run_backtest(cfg, BuySellStrategy(), provider)
    run_dir = generate_report(result, report_output_dir)

    summary = json.loads((run_dir / "summary.json").read_text())
    _, trade_rows = _read_csv(run_dir / "trades.csv")

    expected_return = (summary["final_equity"] - summary["initial_cash"]) / summary["initial_cash"]
    assert summary["total_return_pct"] == pytest.approx(expected_return, abs=1e-10)
    assert summary["max_drawdown"] >= 0
    assert summary["num_trades"] == len(trade_rows)


# ---------------------------------------------------------------------------
# Test 5: run_manifest.json has config
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_report_run_manifest_has_config(
    provider_config: DataProviderConfig,
    provider: LocalFileDataProvider,
    report_output_dir: Path,
) -> None:
    """run_manifest.json has config fields. Parseable, round-trips via BacktestConfig.from_dict."""
    cfg = _engine_config(provider_config)
    result = run_backtest(cfg, NullStrategy(), provider)
    run_dir = generate_report(result, report_output_dir, provider=provider)

    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    assert "config" in manifest
    assert manifest["config"]["symbol"] == "SPY"
    assert manifest["config"]["timeframe_base"] == "1m"
    assert "run_id" in manifest

    restored = BacktestConfig.from_dict(manifest["config"])
    assert restored.symbol == "SPY"


# ---------------------------------------------------------------------------
# Test 6: Determinism — identical runs → identical output files
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_report_determinism(
    provider_config: DataProviderConfig,
    report_output_dir: Path,
) -> None:
    """Two identical runs produce identical CSV/JSON content (A5).
    Compare file contents (excluding git_hash which may vary)."""
    cfg = _engine_config(provider_config)

    p1 = LocalFileDataProvider(provider_config)
    r1 = run_backtest(cfg, NullStrategy(), p1)
    dir1 = generate_report(r1, report_output_dir / "run1")

    p2 = LocalFileDataProvider(provider_config)
    r2 = run_backtest(cfg, NullStrategy(), p2)
    dir2 = generate_report(r2, report_output_dir / "run2")

    for csv_name in ["equity_curve.csv", "orders.csv", "fills.csv", "trades.csv"]:
        content1 = (dir1 / csv_name).read_text()
        content2 = (dir2 / csv_name).read_text()
        assert content1 == content2, f"{csv_name} differs between runs"

    s1 = json.loads((dir1 / "summary.json").read_text())
    s2 = json.loads((dir2 / "summary.json").read_text())
    assert s1 == s2


# ---------------------------------------------------------------------------
# Test 7: Fees appear in fills and summary
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_report_with_fees(
    provider_config: DataProviderConfig,
    provider: LocalFileDataProvider,
    report_output_dir: Path,
) -> None:
    """FeeModelConfig applied. summary.json total_fees > 0. fills.csv fees column populated."""
    fee_cfg = FeeModelConfig(per_contract=0.65, per_order=0.50)
    cfg = _engine_config(provider_config, fee_config=fee_cfg)
    result = run_backtest(cfg, BuyOnceStrategy(), provider)
    run_dir = generate_report(result, report_output_dir)

    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["total_fees"] > 0

    _, fill_rows = _read_csv(run_dir / "fills.csv")
    assert len(fill_rows) == 1
    assert float(fill_rows[0]["fees"]) > 0
