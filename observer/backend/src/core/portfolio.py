"""PortfolioState — portfolio snapshot for strategy decisions.

Observer uses a minimal shape (cash, positions) for MVP. Mock implementation
returns empty state; replace with real source when observer becomes portfolio-aware.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Position:
    """Single position: instrument_id, qty, avg_price.

    Aligns with strategizer PositionView. Observer may extend with
    multiplier, instrument_type when needed.
    """

    instrument_id: str
    qty: int
    avg_price: float


@dataclass
class PortfolioState:
    """Portfolio state at a point in time: cash, positions.

    Observer may extend with realized_pnl, unrealized_pnl, equity when needed.
    """

    cash: float
    positions: dict[str, Position]  # symbol/instrument_id -> Position


def create_mock_portfolio() -> PortfolioState:
    """Empty portfolio for MVP. Replace with real source when portfolio-aware."""
    return PortfolioState(cash=0.0, positions={})
