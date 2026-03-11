"""Summary metrics — aggregate statistics from a BacktestResult.

Reasoning: SummaryMetrics collects return, drawdown, win rate, and fee totals
for summary.json output. All values are derivable from BacktestResult + trades;
no hidden state. compute_summary is a pure function.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.engine.result import BacktestResult
from src.reporter.trades import derive_trades


@dataclass
class SummaryMetrics:
    """Aggregate performance metrics for a single backtest run.

    Reasoning: all fields are JSON-serializable scalars. to_dict() produces
    the summary.json content. Datetimes stored as ISO strings.
    """

    initial_cash: float
    final_equity: float
    total_return_pct: float
    realized_pnl: float
    unrealized_pnl: float
    max_drawdown: float
    max_drawdown_pct: float
    num_trades: int
    num_winning: int
    num_losing: int
    win_rate: float
    total_fees: float
    start: str
    end: str
    num_steps: int
    elapsed_seconds: float | None = None

    def to_dict(self) -> dict:
        """Return JSON-serializable dict of all fields."""
        d = {
            "initial_cash": self.initial_cash,
            "final_equity": self.final_equity,
            "total_return_pct": self.total_return_pct,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "num_trades": self.num_trades,
            "num_winning": self.num_winning,
            "num_losing": self.num_losing,
            "win_rate": self.win_rate,
            "total_fees": self.total_fees,
            "start": self.start,
            "end": self.end,
            "num_steps": self.num_steps,
        }
        if self.elapsed_seconds is not None:
            d["elapsed_seconds"] = round(self.elapsed_seconds, 2)
        return d


def compute_summary(result: BacktestResult) -> SummaryMetrics:
    """Derive aggregate metrics from a BacktestResult.

    Reasoning: calls derive_trades internally to get trade list for win/loss
    analysis. Drawdown computed from equity curve. All arithmetic is
    deterministic (A5).
    """
    initial_cash = result.config.initial_cash
    final_equity = result.equity_curve[-1].equity if result.equity_curve else initial_cash

    total_return_pct = (final_equity - initial_cash) / initial_cash if initial_cash else 0.0

    max_dd, max_dd_pct = _compute_max_drawdown(result)

    # Build open_marks so open positions count in trade statistics
    open_marks = None
    if result.final_marks and result.equity_curve:
        last_ts = result.equity_curve[-1].ts
        open_marks = {k: (v, last_ts) for k, v in result.final_marks.items()}
    inst_mults = result.instrument_multipliers or None
    trades = derive_trades(
        result.fills, result.orders,
        open_marks=open_marks, instrument_multipliers=inst_mults,
    )
    closed_trades = [t for t in trades if not t.is_open]
    num_winning = sum(1 for t in closed_trades if t.realized_pnl > 0)
    num_losing = sum(1 for t in closed_trades if t.realized_pnl <= 0)
    win_rate = num_winning / len(closed_trades) if closed_trades else 0.0

    total_fees = sum(f.fees for f in result.fills)
    realized_pnl = sum(t.realized_pnl for t in closed_trades)

    portfolio = result.final_portfolio
    unrealized_pnl = portfolio.unrealized_pnl if portfolio else 0.0

    start_str = result.config.start.isoformat() if result.config.start else ""
    end_str = result.config.end.isoformat() if result.config.end else ""

    return SummaryMetrics(
        initial_cash=initial_cash,
        final_equity=final_equity,
        total_return_pct=total_return_pct,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        max_drawdown=max_dd,
        max_drawdown_pct=max_dd_pct,
        num_trades=len(closed_trades),
        num_winning=num_winning,
        num_losing=num_losing,
        win_rate=win_rate,
        total_fees=total_fees,
        start=start_str,
        end=end_str,
        num_steps=len(result.equity_curve),
    )


def _compute_max_drawdown(result: BacktestResult) -> tuple[float, float]:
    """Peak-to-trough drawdown from equity curve.

    Reasoning: track running peak; drawdown = peak - current. Return both
    absolute and percentage. Zero if fewer than 2 points.
    """
    if len(result.equity_curve) < 2:
        return 0.0, 0.0

    peak = result.equity_curve[0].equity
    max_dd = 0.0
    max_dd_pct = 0.0

    for point in result.equity_curve:
        if point.equity > peak:
            peak = point.equity
        dd = peak - point.equity
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = dd / peak if peak else 0.0

    return max_dd, max_dd_pct
