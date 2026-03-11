"""Engine: backtest loop, strategy ABC, result container.

Reasoning: Central module for A3 simulation loop. Wires Clock, DataProvider,
Strategy, Broker, Portfolio. Exports run_backtest as the main entry point.
"""

from src.engine.engine import run_backtest
from src.engine.result import BacktestResult, EquityPoint
from src.engine.strategy import NullStrategy, Strategy

__all__ = [
    "BacktestResult",
    "EquityPoint",
    "NullStrategy",
    "Strategy",
    "run_backtest",
]
