# Reporter: generate run artifacts from BacktestResult.

from src.reporter.reporter import (
    generate_report,
    write_equity_curve,
    write_fills,
    write_orders,
    write_run_manifest,
    write_summary,
    write_trades,
)
from src.reporter.summary import SummaryMetrics, compute_summary
from src.reporter.trades import Trade, derive_trades

__all__ = [
    "Trade",
    "SummaryMetrics",
    "derive_trades",
    "compute_summary",
    "generate_report",
    "write_equity_curve",
    "write_orders",
    "write_fills",
    "write_trades",
    "write_summary",
    "write_run_manifest",
]
