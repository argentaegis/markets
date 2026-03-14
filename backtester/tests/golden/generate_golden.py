#!/usr/bin/env python3
"""Generate golden test files from fixture data.

Run: python tests/golden/generate_golden.py

Reasoning: captures known-good output for regression detection. Produces
expected_*.json and expected_*.csv files that test_golden.py compares against.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.domain.config import BacktestConfig
from src.engine.engine import run_backtest
from src.loader.provider import DataProviderConfig, LocalFileDataProvider
from src.reporter.reporter import generate_report
from src.reporter.summary import compute_summary
from src.reporter.trades import derive_trades
from src.strategies.strategizer_adapter import StrategizerStrategy

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "src" / "loader" / "tests" / "fixtures"
GOLDEN_DIR = Path(__file__).resolve().parent


def _utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 2, hour, minute, tzinfo=timezone.utc)


def _provider_config() -> DataProviderConfig:
    return DataProviderConfig(
        underlying_path=FIXTURES_ROOT / "underlying",
        options_path=FIXTURES_ROOT / "options",
        timeframes_supported=["1d", "1h", "1m"],
        missing_data_policy="RETURN_PARTIAL",
        max_quote_age=None,
    )


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


CONTRACT = "SPY|2026-01-17|C|480|100"


def generate() -> None:
    pc = _provider_config()

    # --- BuyAndHold ---
    cfg_bh = _engine_config(pc)
    provider_bh = LocalFileDataProvider(pc)
    strategy_bh = StrategizerStrategy("buy_and_hold", {"contract_id": CONTRACT}, config=cfg_bh)
    result_bh = run_backtest(cfg_bh, strategy_bh, provider_bh)
    summary_bh = compute_summary(result_bh)

    with open(GOLDEN_DIR / "expected_buy_and_hold_summary.json", "w") as f:
        json.dump(summary_bh.to_dict(), f, indent=2)
        f.write("\n")

    with open(GOLDEN_DIR / "expected_buy_and_hold_equity.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ts", "equity"])
        for ep in result_bh.equity_curve:
            writer.writerow([ep.ts.isoformat(), ep.equity])

    # --- CoveredCall (Plan 267: true covered call — hold shares, sell calls) ---
    cfg_cc = _engine_config(pc)
    provider_cc = LocalFileDataProvider(pc)
    strategy_cc = StrategizerStrategy(
        "covered_call",
        {"symbol": "SPY", "shares_per_contract": 100, "contract_id": CONTRACT},
        config=cfg_cc,
    )
    result_cc = run_backtest(cfg_cc, strategy_cc, provider_cc)
    summary_cc = compute_summary(result_cc)
    open_marks_cc = None
    if result_cc.final_marks and result_cc.equity_curve:
        last_ts = result_cc.equity_curve[-1].ts
        open_marks_cc = {k: (v, last_ts) for k, v in result_cc.final_marks.items()}
    trades_cc = derive_trades(
        result_cc.fills, result_cc.orders,
        open_marks=open_marks_cc,
        instrument_multipliers=result_cc.instrument_multipliers,
    )

    with open(GOLDEN_DIR / "expected_covered_call_summary.json", "w") as f:
        json.dump(summary_cc.to_dict(), f, indent=2)
        f.write("\n")

    with open(GOLDEN_DIR / "expected_covered_call_trades.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["instrument_id", "side", "qty", "entry_price", "exit_price", "realized_pnl", "fees"])
        for t in trades_cc:
            writer.writerow([t.instrument_id, t.side, t.qty, t.entry_price, t.exit_price, t.realized_pnl, t.fees])

    # --- CoveredCall with fees ---
    cfg_fees = _engine_config(pc, broker="tdameritrade")
    provider_fees = LocalFileDataProvider(pc)
    strategy_fees = StrategizerStrategy(
        "covered_call",
        {"symbol": "SPY", "shares_per_contract": 100, "contract_id": CONTRACT},
        config=cfg_fees,
    )
    result_fees = run_backtest(cfg_fees, strategy_fees, provider_fees)
    summary_fees = compute_summary(result_fees)

    with open(GOLDEN_DIR / "expected_covered_call_fees_summary.json", "w") as f:
        json.dump(summary_fees.to_dict(), f, indent=2)
        f.write("\n")

    print(f"Golden files written to {GOLDEN_DIR}")
    print(f"  BuyAndHold: summary={summary_bh.num_steps} steps, equity={summary_bh.final_equity}")
    print(f"  CoveredCall: {len(trades_cc)} trades, realized_pnl={summary_cc.realized_pnl}")
    print(f"  CoveredCall+fees: total_fees={summary_fees.total_fees}")


if __name__ == "__main__":
    generate()
