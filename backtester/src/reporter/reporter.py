"""Reporter — write BacktestResult artifacts to runs/{run_id}/.

Reasoning: pure functions for each writer (data + path → file). csv.DictWriter
for CSVs, json.dump for JSON. generate_report is the single entry point that
orchestrates all writers. Datetimes formatted as ISO strings (A5 determinism).
"""

from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from src.domain.config import BacktestConfig
from src.domain.fill import Fill
from src.domain.order import Order
from src.engine.result import BacktestResult, EquityPoint
from src.reporter.summary import SummaryMetrics, compute_summary
from src.reporter.trades import Trade, derive_trades
from src.reporter.visualize import generate_html_report


# ── CSV Writers ──────────────────────────────────────────────────────────


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Shared helper: write a list of dicts as CSV with header row.

    Reasoning: eliminates repetition across writers. Always writes header
    even when rows is empty (produces header-only CSV).
    """
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_equity_curve(path: Path, equity_curve: list[EquityPoint]) -> None:
    """Write equity_curve.csv: ts, equity per timestamp."""
    _write_csv(
        path,
        fieldnames=["ts", "equity"],
        rows=[{"ts": ep.ts.isoformat(), "equity": ep.equity} for ep in equity_curve],
    )


def write_orders(path: Path, orders: list[Order]) -> None:
    """Write orders.csv: all Order fields."""
    _write_csv(
        path,
        fieldnames=["id", "ts", "instrument_id", "side", "qty", "order_type", "limit_price", "tif"],
        rows=[
            {
                "id": o.id,
                "ts": o.ts.isoformat(),
                "instrument_id": o.instrument_id,
                "side": o.side,
                "qty": o.qty,
                "order_type": o.order_type,
                "limit_price": o.limit_price if o.limit_price is not None else "",
                "tif": o.tif,
            }
            for o in orders
        ],
    )


def write_fills(path: Path, fills: list[Fill]) -> None:
    """Write fills.csv: all Fill fields."""
    _write_csv(
        path,
        fieldnames=["order_id", "ts", "fill_price", "fill_qty", "fees", "liquidity_flag"],
        rows=[
            {
                "order_id": f.order_id,
                "ts": f.ts.isoformat(),
                "fill_price": f.fill_price,
                "fill_qty": f.fill_qty,
                "fees": f.fees,
                "liquidity_flag": f.liquidity_flag or "",
            }
            for f in fills
        ],
    )


def write_trades(path: Path, trades: list[Trade]) -> None:
    """Write trades.csv: all Trade fields."""
    _write_csv(
        path,
        fieldnames=[
            "instrument_id", "side", "qty", "entry_ts", "entry_price",
            "exit_ts", "exit_price", "realized_pnl", "fees", "multiplier", "is_open",
        ],
        rows=[
            {
                "instrument_id": t.instrument_id,
                "side": t.side,
                "qty": t.qty,
                "entry_ts": t.entry_ts.isoformat(),
                "entry_price": t.entry_price,
                "exit_ts": t.exit_ts.isoformat(),
                "exit_price": t.exit_price,
                "realized_pnl": t.realized_pnl,
                "fees": t.fees,
                "multiplier": t.multiplier,
                "is_open": str(t.is_open).lower(),
            }
            for t in trades
        ],
    )


# ── JSON Writers ─────────────────────────────────────────────────────────


def write_summary(path: Path, summary: SummaryMetrics) -> None:
    """Write summary.json from SummaryMetrics.to_dict()."""
    with open(path, "w") as f:
        json.dump(summary.to_dict(), f, indent=2)
        f.write("\n")


def write_run_manifest(
    path: Path,
    config: BacktestConfig,
    *,
    run_id: str,
    provider_data: dict | None = None,
) -> None:
    """Write run_manifest.json: config snapshot, provider diagnostics, git hash."""
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "config": config.to_dict(),
        "provider_diagnostics": provider_data,
        "git_hash": _get_git_hash(),
    }
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2, default=_json_default)
        f.write("\n")


def _json_default(obj: Any) -> Any:
    """JSON encoder fallback: datetimes → ISO strings, Paths → strings.

    Reasoning: provider diagnostics may contain datetime and Path objects.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _get_git_hash() -> str | None:
    """Best-effort git short hash. None if not in a repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


# ── Orchestration ────────────────────────────────────────────────────────


def _build_open_marks(result: BacktestResult) -> dict[str, tuple[float, datetime]] | None:
    """Build open_marks from BacktestResult for open-position trade emission.

    Reasoning: open positions at run end should appear in trades.csv marked
    to their final price. Uses final_marks from the engine (last step's
    extract_marks output) and the last equity curve timestamp.
    """
    if not result.final_marks or not result.equity_curve:
        return None
    last_ts = result.equity_curve[-1].ts
    return {
        instrument_id: (mark_price, last_ts)
        for instrument_id, mark_price in result.final_marks.items()
    }


def _make_run_id(config: BacktestConfig) -> str:
    """Deterministic, filesystem-safe run_id from config fields.

    Format: {symbol}_{timeframe}_{start_date}_{end_date}
    """
    start_date = config.start.strftime("%Y%m%d") if config.start else "unknown"
    end_date = config.end.strftime("%Y%m%d") if config.end else "unknown"
    return f"{config.symbol}_{config.timeframe_base}_{start_date}_{end_date}"


def _run_id_with_timestamp(base_run_id: str, run_timestamp: datetime) -> str:
    """Prefix run_id with YYYYMMDDHHmm for sortable, unique run folders."""
    ts_str = run_timestamp.strftime("%Y%m%d%H%M")
    return f"{ts_str}_{base_run_id}"


def generate_report(
    result: BacktestResult,
    output_dir: Path,
    *,
    provider: Any | None = None,
    run_timestamp: datetime | None = None,
    elapsed_seconds: float | None = None,
) -> Path:
    """Create {output_dir}/{run_id}/ with all 7 artifact files.

    Reasoning: single entry point for Reporter. Callers pass BacktestResult
    and an output directory; generate_report handles directory creation,
    trade derivation, summary computation, and all file writes.
    Callers control the parent directory (e.g. runs/, test_runs/).

    Returns path to the created run directory.
    """
    base_run_id = _make_run_id(result.config)
    run_id = _run_id_with_timestamp(base_run_id, run_timestamp) if run_timestamp else base_run_id
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Derive trades and summary (include open positions marked to final price)
    open_marks = _build_open_marks(result)
    inst_mults = result.instrument_multipliers or None
    trades = derive_trades(
        result.fills, result.orders,
        open_marks=open_marks, instrument_multipliers=inst_mults,
    )
    summary = compute_summary(result)
    if elapsed_seconds is not None:
        summary = SummaryMetrics(
            initial_cash=summary.initial_cash,
            final_equity=summary.final_equity,
            total_return_pct=summary.total_return_pct,
            realized_pnl=summary.realized_pnl,
            unrealized_pnl=summary.unrealized_pnl,
            max_drawdown=summary.max_drawdown,
            max_drawdown_pct=summary.max_drawdown_pct,
            num_trades=summary.num_trades,
            num_winning=summary.num_winning,
            num_losing=summary.num_losing,
            win_rate=summary.win_rate,
            total_fees=summary.total_fees,
            start=summary.start,
            end=summary.end,
            num_steps=summary.num_steps,
            elapsed_seconds=elapsed_seconds,
        )

    # Provider diagnostics
    provider_data = None
    if provider is not None and hasattr(provider, "get_run_manifest_data"):
        provider_data = provider.get_run_manifest_data()

    # Write all artifacts
    write_equity_curve(run_dir / "equity_curve.csv", result.equity_curve)
    write_orders(run_dir / "orders.csv", result.orders)
    write_fills(run_dir / "fills.csv", result.fills)
    write_trades(run_dir / "trades.csv", trades)
    write_summary(run_dir / "summary.json", summary)
    write_run_manifest(run_dir / "run_manifest.json", result.config, run_id=run_id, provider_data=provider_data)

    # Generate interactive HTML report from the artifacts just written
    generate_html_report(run_dir)

    return run_dir
