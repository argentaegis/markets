"""Clock module — generates simulation timestamps (bar-close times) for the backtest loop.

iter_times(start, end, timeframe_base) -> Iterable[datetime]
"""

from src.clock.clock import count_times, iter_times

__all__ = ["count_times", "iter_times"]
