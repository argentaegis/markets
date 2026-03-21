"""Reporter writer tests — Phases 3 and 4 of 080.

Reasoning: each writer is a pure function (data + path → file). Tests verify
correct CSV columns/rows and JSON structure using tmp_path fixture.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.domain.config import BacktestConfig
from src.domain.fill import Fill
from src.domain.order import Order
from src.engine.result import BacktestResult, EquityPoint
from src.reporter.reporter import (
    generate_report,
    write_equity_curve,
    write_fills,
    write_orders,
    write_run_manifest,
    write_summary,
    write_trades,
)
from src.reporter.summary import SummaryMetrics
from src.reporter.trades import Trade


def _utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 2, hour, minute, tzinfo=timezone.utc)


# ── Phase 3: individual writers ──────────────────────────────────────────


class TestWriteEquityCurve:
    def test_csv_columns_and_rows(self, tmp_path: Path) -> None:
        """write_equity_curve writes CSV with ts,equity columns."""
        curve = [
            EquityPoint(ts=_utc(14, 31), equity=100_000.0),
            EquityPoint(ts=_utc(14, 32), equity=99_850.0),
        ]
        path = tmp_path / "equity_curve.csv"
        write_equity_curve(path, curve)

        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert reader.fieldnames == ["ts", "equity"]
        assert len(rows) == 2
        assert rows[0]["equity"] == "100000.0"


class TestWriteOrders:
    def test_csv_columns_and_rows(self, tmp_path: Path) -> None:
        """write_orders writes CSV with all Order fields."""
        orders = [
            Order(id="buy-1", ts=_utc(14, 31), instrument_id="SPY|C|480", side="BUY", qty=1, order_type="market"),
        ]
        path = tmp_path / "orders.csv"
        write_orders(path, orders)

        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert "id" in reader.fieldnames
        assert "instrument_id" in reader.fieldnames
        assert len(rows) == 1
        assert rows[0]["side"] == "BUY"


class TestWriteFills:
    def test_csv_columns_and_rows(self, tmp_path: Path) -> None:
        """write_fills writes CSV with all Fill fields."""
        fills = [
            Fill(order_id="buy-1", ts=_utc(14, 31), fill_price=5.30, fill_qty=1, fees=1.15),
        ]
        path = tmp_path / "fills.csv"
        write_fills(path, fills)

        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert "order_id" in reader.fieldnames
        assert "fees" in reader.fieldnames
        assert len(rows) == 1
        assert rows[0]["fill_price"] == "5.3"


class TestWriteTrades:
    def test_csv_columns_and_rows(self, tmp_path: Path) -> None:
        """write_trades writes CSV matching Trade fields."""
        trades = [
            Trade(
                instrument_id="SPY|C|480",
                side="LONG",
                qty=1,
                entry_ts=_utc(14, 31),
                entry_price=5.30,
                exit_ts=_utc(14, 32),
                exit_price=5.50,
                realized_pnl=20.0,
                fees=2.30,
                multiplier=100.0,
            ),
        ]
        path = tmp_path / "trades.csv"
        write_trades(path, trades)

        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert "instrument_id" in reader.fieldnames
        assert "realized_pnl" in reader.fieldnames
        assert len(rows) == 1
        assert rows[0]["side"] == "LONG"


class TestWriteSummary:
    def test_json_matches_to_dict(self, tmp_path: Path) -> None:
        """write_summary writes JSON matching SummaryMetrics.to_dict()."""
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
        path = tmp_path / "summary.json"
        write_summary(path, sm)

        data = json.loads(path.read_text())
        assert data == sm.to_dict()


class TestWriteRunManifest:
    def test_json_has_config_and_git_hash(self, tmp_path: Path) -> None:
        """write_run_manifest writes JSON with config, diagnostics, git_hash."""
        from src.loader.config import DataProviderConfig
        config = BacktestConfig(
            symbol="SPY",
            start=_utc(14, 30),
            end=_utc(14, 35),
            timeframe_base="1m",
            data_provider_config=DataProviderConfig(underlying_path="", options_path=""),
            broker="zero",
        )
        path = tmp_path / "run_manifest.json"
        write_run_manifest(path, config, run_id="SPY_1m_20260102_20260102", provider_data={"files_loaded": 3})

        data = json.loads(path.read_text())
        assert data["run_id"] == "SPY_1m_20260102_20260102"
        assert "config" in data
        assert data["config"]["symbol"] == "SPY"
        assert data["provider_diagnostics"]["files_loaded"] == 3
        assert "git_hash" in data


# ── Phase 4: generate_report orchestration ───────────────────────────────


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


def _make_result() -> BacktestResult:
    config = _make_config()
    return BacktestResult(
        config=config,
        equity_curve=[
            EquityPoint(ts=_utc(14, 30), equity=100_000.0),
            EquityPoint(ts=_utc(14, 31), equity=100_050.0),
        ],
        orders=[
            Order(id="b1", ts=_utc(14, 31), instrument_id="SPY|C|480", side="BUY", qty=1, order_type="market"),
        ],
        fills=[
            Fill(order_id="b1", ts=_utc(14, 31), fill_price=5.30, fill_qty=1, fees=1.15),
        ],
    )


class TestGenerateReport:
    def test_creates_run_directory_with_all_files(self, tmp_path: Path) -> None:
        """generate_report creates runs/{run_id}/ with all 7 files."""
        result = _make_result()
        run_dir = generate_report(result, tmp_path)

        assert run_dir.exists()
        expected_files = {
            "equity_curve.csv",
            "allocations.csv",
            "orders.csv",
            "fills.csv",
            "trades.csv",
            "summary.json",
            "run_manifest.json",
            "report.html",
        }
        actual_files = {f.name for f in run_dir.iterdir()}
        assert expected_files == actual_files

    def test_run_id_derived_from_config(self, tmp_path: Path) -> None:
        """run_id is deterministic from config fields."""
        result = _make_result()
        run_dir = generate_report(result, tmp_path)
        assert "SPY" in run_dir.name
        assert "1m" in run_dir.name

    def test_files_non_empty_and_parseable(self, tmp_path: Path) -> None:
        """Each output file is non-empty and parseable."""
        result = _make_result()
        run_dir = generate_report(result, tmp_path)

        for csv_name in ["equity_curve.csv", "orders.csv", "fills.csv", "trades.csv"]:
            content = (run_dir / csv_name).read_text()
            assert len(content) > 0

        for json_name in ["summary.json", "run_manifest.json"]:
            data = json.loads((run_dir / json_name).read_text())
            assert isinstance(data, dict)

    def test_without_provider(self, tmp_path: Path) -> None:
        """generate_report without provider omits provider diagnostics."""
        result = _make_result()
        run_dir = generate_report(result, tmp_path, provider=None)
        manifest = json.loads((run_dir / "run_manifest.json").read_text())
        assert manifest["provider_diagnostics"] is None

    def test_returns_run_directory_path(self, tmp_path: Path) -> None:
        """generate_report returns the path to the run directory."""
        result = _make_result()
        run_dir = generate_report(result, tmp_path)
        assert isinstance(run_dir, Path)
        assert run_dir.is_dir()

    def test_run_id_with_timestamp_and_elapsed(self, tmp_path: Path) -> None:
        """generate_report with run_timestamp and elapsed_seconds uses them."""
        result = _make_result()
        run_ts = datetime(2026, 3, 2, 15, 11, 0, tzinfo=timezone.utc)
        run_dir = generate_report(
            result, tmp_path, run_timestamp=run_ts, elapsed_seconds=12.34
        )
        assert run_dir.name.startswith("202603021511_")
        assert "SPY" in run_dir.name
        summary = json.loads((run_dir / "summary.json").read_text())
        assert summary["elapsed_seconds"] == 12.34
