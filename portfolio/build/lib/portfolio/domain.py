"""Domain types: Position, PortfolioState."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Position:
    """Single position: instrument_id, qty, avg_price, multiplier, instrument_type.

    Reasoning: qty/avg_price derived from fills. multiplier critical for contract value
    (options 100 vs minis). instrument_type for marking (option vs underlying).
    """

    instrument_id: str
    qty: int
    avg_price: float
    multiplier: float = 1.0
    instrument_type: str = "equity"  # "equity" | "option" | "future"


@dataclass
class PortfolioState:
    """Portfolio state at a timestamp: cash, positions, realized_pnl, unrealized_pnl, equity.

    Reasoning: realized_pnl from closed fills; unrealized from mark vs avg_cost.
    positions dict enables per-instrument lookup and aggregation.
    Equity invariant: equity == cash + sum(mark_value).
    """

    cash: float
    positions: dict[str, Position]
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    equity: float = 0.0
