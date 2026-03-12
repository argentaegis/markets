"""Summary metrics — aggregate statistics from a BacktestResult.

Reasoning: SummaryMetrics collects return, drawdown, win rate, and fee totals
for summary.json output. All values are derivable from BacktestResult + trades;
no hidden state. compute_summary is a pure function.

Plan 264: Added sharpe (annualized), cagr, turnover, num_open_positions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.engine.result import BacktestResult
from src.reporter.trades import derive_trades


def _annualization_factor(timeframe_base: str) -> int:
    """Periods per year for Sharpe annualization. 1d→252, 1m→252*390, 1h→252*6.5."""
    if timeframe_base == "1d":
        return 252
    if timeframe_base == "1m":
        return 252 * 390
    if timeframe_base == "1h":
        return int(252 * 6.5)
    return 252


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
    num_open_positions: int = 0
    sharpe: float | None = None
    cagr: float | None = None
    turnover: float | None = None
    sharpe_annualization: str | None = None

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
            "num_open_positions": self.num_open_positions,
        }
        if self.elapsed_seconds is not None:
            d["elapsed_seconds"] = round(self.elapsed_seconds, 2)
        if self.sharpe is not None:
            d["sharpe"] = round(self.sharpe, 4)
        else:
            d["sharpe"] = None
        if self.cagr is not None:
            d["cagr"] = round(self.cagr, 6)
        else:
            d["cagr"] = None
        if self.turnover is not None:
            d["turnover"] = round(self.turnover, 4)
        else:
            d["turnover"] = None
        if self.sharpe_annualization is not None:
            d["sharpe_annualization"] = self.sharpe_annualization
        return d


def compute_summary(result: BacktestResult) -> SummaryMetrics:
    """Derive aggregate metrics from a BacktestResult.

    Reasoning: calls derive_trades internally to get trade list for win/loss
    analysis. Drawdown computed from equity curve. All arithmetic is
    deterministic (A5). Plan 264: adds sharpe, cagr, turnover, num_open_positions.
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
        open_marks=open_marks,
        instrument_multipliers=inst_mults,
    )
    closed_trades = [t for t in trades if not t.is_open]
    open_trades = [t for t in trades if t.is_open]
    num_winning = sum(1 for t in closed_trades if t.realized_pnl > 0)
    num_losing = sum(1 for t in closed_trades if t.realized_pnl <= 0)
    win_rate = num_winning / len(closed_trades) if closed_trades else 0.0

    total_fees = sum(f.fees for f in result.fills)
    realized_pnl = sum(t.realized_pnl for t in closed_trades)

    portfolio = result.final_portfolio
    unrealized_pnl = portfolio.unrealized_pnl if portfolio else 0.0

    start_str = result.config.start.isoformat() if result.config.start else ""
    end_str = result.config.end.isoformat() if result.config.end else ""

    # Sharpe (annualized)
    sharpe, sharpe_ann = _compute_sharpe(result)
    cagr = _compute_cagr(result, initial_cash, final_equity)
    turnover = _compute_turnover(result)

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
        num_open_positions=len(open_trades),
        sharpe=sharpe,
        cagr=cagr,
        turnover=turnover,
        sharpe_annualization=sharpe_ann,
    )


def _compute_sharpe(result: BacktestResult) -> tuple[float | None, str | None]:
    """Annualized Sharpe from step returns. Null if <20 obs or zero std."""
    curve = result.equity_curve
    if len(curve) < 2:
        return None, None
    returns = []
    for i in range(1, len(curve)):
        prev = curve[i - 1].equity
        if prev <= 0:
            continue
        r = (curve[i].equity - prev) / prev
        returns.append(r)
    if len(returns) < 20:
        return None, None
    mean_ret = sum(returns) / len(returns)
    variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
    std_ret = math.sqrt(variance)
    if std_ret <= 0:
        return None, None
    raw_sharpe = mean_ret / std_ret
    tf = result.config.timeframe_base or "1d"
    n = _annualization_factor(tf)
    sharpe_ann = raw_sharpe * math.sqrt(n)
    ann_label = f"{tf}/{n}"
    return sharpe_ann, ann_label


def _compute_cagr(result: BacktestResult, initial_cash: float, final_equity: float) -> float | None:
    """CAGR. Null if <1 day or final_equity <= 0."""
    if not result.config.start or not result.config.end:
        return None
    if initial_cash <= 0 or final_equity <= 0:
        return None
    delta = result.config.end - result.config.start
    years = delta.total_seconds() / (365.25 * 86400)
    if years < 1 / 365.25:  # less than 1 day
        return None
    return (final_equity / initial_cash) ** (1 / years) - 1


def _compute_turnover(result: BacktestResult) -> float | None:
    """sum(abs(fill_notional)) / mean(equity). Null if empty equity."""
    if not result.equity_curve:
        return None
    order_by_id = {o.id: o for o in result.orders}
    multipliers = result.instrument_multipliers or {}
    total_notional = 0.0
    for f in result.fills:
        order = order_by_id.get(f.order_id)
        inst = order.instrument_id if order else ""
        mult = multipliers.get(inst, 1.0)
        notional = abs(f.fill_price * f.fill_qty * mult)
        total_notional += notional
    mean_equity = sum(ep.equity for ep in result.equity_curve) / len(result.equity_curve)
    if mean_equity <= 0:
        return None
    return total_notional / mean_equity


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
