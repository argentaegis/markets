"""HTML report visualization tests — Phase 1 of 110.

Reasoning: generate_html_report reads CSVs/JSON from a run directory and
produces a self-contained report.html with Plotly.js charts. Tests verify
file creation, chart sections, summary values, drawdown computation,
and graceful handling of empty trades.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from src.reporter.visualize import _compute_drawdown, _pivot_allocations_by_symbol, generate_html_report


def _write_equity_curve(run_dir: Path, rows: list[dict]) -> None:
    path = run_dir / "equity_curve.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ts", "equity"])
        writer.writeheader()
        writer.writerows(rows)


def _write_trades(run_dir: Path, rows: list[dict]) -> None:
    path = run_dir / "trades.csv"
    fieldnames = [
        "instrument_id", "side", "qty", "entry_ts", "entry_price",
        "exit_ts", "exit_price", "realized_pnl", "fees", "multiplier",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_fills(run_dir: Path, rows: list[dict]) -> None:
    path = run_dir / "fills.csv"
    fieldnames = ["order_id", "ts", "fill_price", "fill_qty", "fees", "liquidity_flag"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_summary(run_dir: Path, data: dict) -> None:
    with open(run_dir / "summary.json", "w") as f:
        json.dump(data, f)


def _write_run_manifest(run_dir: Path, config: dict) -> None:
    with open(run_dir / "run_manifest.json", "w") as f:
        json.dump({"config": config, "run_id": "test_run"}, f)


def _minimal_summary() -> dict:
    return {
        "initial_cash": 100000.0,
        "final_equity": 100172.88,
        "total_return_pct": 0.0017,
        "realized_pnl": 172.88,
        "unrealized_pnl": 172.88,
        "max_drawdown": 116.45,
        "max_drawdown_pct": 0.00116,
        "num_trades": 1,
        "num_winning": 1,
        "num_losing": 0,
        "win_rate": 1.0,
        "total_fees": 0.0,
        "start": "2024-03-01T00:00:00+00:00",
        "end": "2025-12-31T00:00:00+00:00",
        "num_steps": 5,
    }


def _minimal_equity() -> list[dict]:
    return [
        {"ts": "2024-03-01T21:00:00+00:00", "equity": 99998.72},
        {"ts": "2024-03-04T21:00:00+00:00", "equity": 99998.17},
        {"ts": "2024-03-05T21:00:00+00:00", "equity": 99993.05},
        {"ts": "2024-03-06T21:00:00+00:00", "equity": 99995.62},
        {"ts": "2024-03-07T21:00:00+00:00", "equity": 100005.00},
    ]


def _setup_run_dir(tmp_path: Path, *, trades: list[dict] | None = None) -> Path:
    """Create a minimal run directory with all required files."""
    _write_equity_curve(tmp_path, _minimal_equity())
    _write_trades(tmp_path, trades or [])
    _write_fills(tmp_path, [
        {"order_id": "entry-1", "ts": "2024-03-01T21:00:00+00:00", "fill_price": 514.13, "fill_qty": 1, "fees": 0.0, "liquidity_flag": ""},
    ])
    _write_summary(tmp_path, _minimal_summary())
    return tmp_path


def test_html_report_created(tmp_path: Path) -> None:
    """generate_html_report creates report.html in the run directory."""
    _setup_run_dir(tmp_path)
    result = generate_html_report(tmp_path)
    assert result == tmp_path / "report.html"
    assert result.exists()
    content = result.read_text()
    assert len(content) > 100


def test_html_contains_plotly_script(tmp_path: Path) -> None:
    """report.html loads Plotly.js and calls Plotly.newPlot."""
    _setup_run_dir(tmp_path)
    generate_html_report(tmp_path)
    content = (tmp_path / "report.html").read_text()
    assert "<script" in content
    assert "plotly" in content.lower()
    assert "Plotly.newPlot" in content


def test_html_contains_summary_values(tmp_path: Path) -> None:
    """report.html displays key metrics from summary.json."""
    _setup_run_dir(tmp_path)
    generate_html_report(tmp_path)
    content = (tmp_path / "report.html").read_text()
    assert "100,000" in content  # initial_cash
    assert "100,172.88" in content  # final_equity
    assert "116.45" in content  # max_drawdown


def test_drawdown_computation() -> None:
    """_compute_drawdown returns correct peak-to-trough values."""
    equity = [
        {"ts": "t1", "equity": 100.0},
        {"ts": "t2", "equity": 105.0},
        {"ts": "t3", "equity": 102.0},
        {"ts": "t4", "equity": 108.0},
        {"ts": "t5", "equity": 95.0},
    ]
    dd = _compute_drawdown(equity)
    assert len(dd) == 5
    assert dd[0]["drawdown"] == pytest.approx(0.0)   # first point, no drawdown
    assert dd[1]["drawdown"] == pytest.approx(0.0)   # new peak
    assert dd[2]["drawdown"] == pytest.approx(-3.0)   # 105 - 102
    assert dd[3]["drawdown"] == pytest.approx(0.0)   # new peak
    assert dd[4]["drawdown"] == pytest.approx(-13.0)  # 108 - 95


def test_empty_trades_no_trade_chart(tmp_path: Path) -> None:
    """When trades.csv is header-only, trade P&L chart section is omitted."""
    _setup_run_dir(tmp_path, trades=[])
    generate_html_report(tmp_path)
    content = (tmp_path / "report.html").read_text()
    assert "trade-pnl" not in content


def test_report_title_and_metadata_from_manifest(tmp_path: Path) -> None:
    """When run_manifest.json has config, report uses strategy, symbol, asset type for title and summary."""
    _setup_run_dir(tmp_path)
    _write_run_manifest(tmp_path, {
        "strategy_name": "buy_and_hold_underlying",
        "symbol": "SPY",
        "instrument_type": "equity",
    })
    generate_html_report(tmp_path)
    content = (tmp_path / "report.html").read_text()
    assert "buy_and_hold_underlying — SPY (Equity)" in content
    assert "<td>Strategy</td><td>buy_and_hold_underlying</td>" in content
    assert "<td>Symbol</td><td>SPY</td>" in content
    assert "<td>Asset Type</td><td>Equity</td>" in content


# ---------------------------------------------------------------------------
# Per-symbol equity overlay tests
# ---------------------------------------------------------------------------


def _write_allocations(run_dir: Path, rows: list[dict]) -> None:
    path = run_dir / "allocations.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ts", "instrument_id", "position_value"])
        writer.writeheader()
        writer.writerows(rows)


def _minimal_allocations_multi() -> list[dict]:
    """Two-symbol allocation rows aligned with _minimal_equity() timestamps."""
    eq = _minimal_equity()
    rows = []
    for i, ep in enumerate(eq):
        rows.append({"ts": ep["ts"], "instrument_id": "SPY", "position_value": 50000.0 + i * 10})
        rows.append({"ts": ep["ts"], "instrument_id": "QQQ", "position_value": 40000.0 - i * 5})
    return rows


def test_pivot_returns_empty_for_single_symbol() -> None:
    """_pivot_allocations_by_symbol returns {} when only one instrument present."""
    equity = _minimal_equity()
    allocations = [{"ts": ep["ts"], "instrument_id": "SPY", "position_value": "50000"} for ep in equity]
    result = _pivot_allocations_by_symbol(allocations, equity)
    assert result == {}


def test_pivot_returns_empty_for_no_allocations() -> None:
    """_pivot_allocations_by_symbol returns {} when allocations list is empty."""
    result = _pivot_allocations_by_symbol([], _minimal_equity())
    assert result == {}


def test_pivot_multi_symbol_returns_correct_structure() -> None:
    """_pivot_allocations_by_symbol returns {inst_id: {ts: value}} for 2+ instruments."""
    equity = _minimal_equity()
    allocations = _minimal_allocations_multi()
    result = _pivot_allocations_by_symbol(allocations, equity)
    assert set(result.keys()) == {"SPY", "QQQ"}
    assert len(result["SPY"]) == len(equity)
    assert result["SPY"][equity[0]["ts"]] == pytest.approx(50000.0)
    assert result["QQQ"][equity[0]["ts"]] == pytest.approx(40000.0)


def test_single_symbol_equity_chart_label_is_equity(tmp_path: Path) -> None:
    """Single-symbol run: equity curve trace is named 'Equity', no per-symbol lines."""
    _setup_run_dir(tmp_path)
    generate_html_report(tmp_path)
    content = (tmp_path / "report.html").read_text()
    assert "name: 'Equity'" in content
    assert "name: 'Total'" not in content


def test_multi_symbol_equity_chart_label_is_total(tmp_path: Path) -> None:
    """Multi-symbol run: combined equity trace renamed to 'Total'."""
    _setup_run_dir(tmp_path)
    _write_allocations(tmp_path, _minimal_allocations_multi())
    generate_html_report(tmp_path)
    content = (tmp_path / "report.html").read_text()
    assert "name: 'Total'" in content
    assert "name: 'Equity'" not in content


def test_multi_symbol_equity_chart_has_per_symbol_traces(tmp_path: Path) -> None:
    """Multi-symbol run: per-symbol dashed lines with 0.5 opacity appear in chart."""
    _setup_run_dir(tmp_path)
    _write_allocations(tmp_path, _minimal_allocations_multi())
    generate_html_report(tmp_path)
    content = (tmp_path / "report.html").read_text()
    assert "name: 'SPY'" in content
    assert "name: 'QQQ'" in content
    assert "dash: 'dot'" in content
    assert "opacity: 0.5" in content
