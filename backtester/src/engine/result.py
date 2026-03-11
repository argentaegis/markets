"""BacktestResult and EquityPoint — engine output containers.

Reasoning: BacktestResult collects all outputs from a single backtest run.
Reporter (Step 7) consumes it to produce CSV/JSON artifacts. EquityPoint
records per-timestamp equity for the equity curve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.config import BacktestConfig
from src.domain.event import Event
from src.domain.fill import Fill
from src.domain.order import Order
from src.domain.portfolio import PortfolioState


@dataclass
class EquityPoint:
    """Single point on the equity curve: timestamp and equity value.

    Reasoning: One point per Clock tick. Enables equity_curve.csv and
    drawdown/return calculations in Reporter.
    """

    ts: datetime
    equity: float


@dataclass
class BacktestResult:
    """All outputs from a backtest run.

    Reasoning: Plain dataclass — Reporter (Step 7) consumes fields to
    produce CSV/JSON. Golden test (Step 8) compares results for determinism.
    No methods beyond data access; processing belongs in Reporter.
    """

    config: BacktestConfig
    equity_curve: list[EquityPoint] = field(default_factory=list)
    orders: list[Order] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    final_portfolio: PortfolioState | None = None
    final_marks: dict[str, float] = field(default_factory=dict)
    instrument_multipliers: dict[str, float] = field(default_factory=dict)
