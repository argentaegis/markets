"""CLI runner integration tests — Phase 4 of 090.

Reasoning: run_backtest_cli is the user-facing entry point. Tests verify
it wires config -> engine -> reporter correctly and handles errors.
Uses dedicated configs in tests/configs/ that point to loader fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.runner import run_backtest_cli

CONFIGS_DIR = Path(__file__).resolve().parents[1] / "configs"


@pytest.mark.integration
def test_cli_returns_run_directory(tmp_path: Path, strategizer_required: None) -> None:
    """run_backtest_cli returns a Path to the run directory."""
    config_path = CONFIGS_DIR / "covered_call.yaml"
    run_dir = run_backtest_cli(config_path, tmp_path / "output")
    assert isinstance(run_dir, Path)
    assert run_dir.is_dir()


@pytest.mark.integration
def test_cli_produces_all_seven_files(tmp_path: Path, strategizer_required: None) -> None:
    """Given valid YAML config, produces all 7 report files."""
    config_path = CONFIGS_DIR / "covered_call.yaml"
    run_dir = run_backtest_cli(config_path, tmp_path / "output")

    expected = {"equity_curve.csv", "orders.csv", "fills.csv", "trades.csv", "summary.json", "run_manifest.json", "report.html"}
    actual = {f.name for f in run_dir.iterdir()}
    assert expected == actual


@pytest.mark.integration
def test_cli_invalid_config_raises(tmp_path: Path) -> None:
    """Invalid config file raises clear error."""
    bad_path = tmp_path / "nonexistent.yaml"
    with pytest.raises((FileNotFoundError, ValueError)):
        run_backtest_cli(bad_path, tmp_path / "output")


@pytest.mark.integration
def test_cli_creates_output_directory(tmp_path: Path, strategizer_required: None) -> None:
    """Output directory is created if it doesn't exist."""
    config_path = CONFIGS_DIR / "covered_call.yaml"
    output_dir = tmp_path / "new_output_dir"
    assert not output_dir.exists()
    run_dir = run_backtest_cli(config_path, output_dir)
    assert run_dir.is_dir()


@pytest.mark.integration
def test_cli_buy_and_hold_strategy(tmp_path: Path, strategizer_required: None) -> None:
    """CLI supports buy_and_hold strategy name."""
    config_path = CONFIGS_DIR / "buy_and_hold.yaml"
    run_dir = run_backtest_cli(config_path, tmp_path / "output")
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["num_trades"] == 0  # no closed trades; open position excluded from count


@pytest.mark.integration
def test_cli_with_fees(tmp_path: Path, strategizer_required: None) -> None:
    """CLI supports broker in YAML."""
    config_path = CONFIGS_DIR / "with_fees.yaml"
    run_dir = run_backtest_cli(config_path, tmp_path / "output")
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["total_fees"] > 0
