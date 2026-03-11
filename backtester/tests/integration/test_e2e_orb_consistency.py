"""E2E validation: backtester ORB produces expected entry (130)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.domain.config import BacktestConfig
from src.engine.engine import run_backtest
from src.loader.provider import DataProviderConfig, LocalFileDataProvider
from src.strategies.strategizer_adapter import StrategizerStrategy

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "src" / "loader" / "tests" / "fixtures"

EXPECTED_ENTRY_PRICE = 5410.25  # OR high + 1 tick


def _run_backtester_orb():
    """Run backtester with golden config; return (orders, fills)."""
    from datetime import time

    from src.domain.futures import FuturesContractSpec, TradingSession

    session = TradingSession("RTH", time(9, 30), time(16, 0), "America/New_York")
    fc = FuturesContractSpec(symbol="ESH1", tick_size=0.25, point_value=50.0, session=session)
    dp = DataProviderConfig(
        underlying_path=FIXTURES_ROOT / "underlying",
        options_path=FIXTURES_ROOT / "options",
        timeframes_supported=["1d", "1h", "1m"],
        missing_data_policy="RETURN_PARTIAL",
        max_quote_age=None,
    )
    config = BacktestConfig(
        symbol="ESH1",
        start=datetime(2026, 1, 2, 14, 31, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, 14, 36, tzinfo=timezone.utc),  # Single breakout step
        timeframe_base="1m",
        data_provider_config=dp,
        initial_cash=500_000.0,
        instrument_type="future",
        futures_contract_spec=fc,
    )
    provider = LocalFileDataProvider(dp)
    strategy = StrategizerStrategy("orb_5m", {"qty": 1}, config=config)
    result = run_backtest(config, strategy, provider)
    return result.orders, result.fills


@pytest.mark.integration
def test_orb_backtester_entry_matches_expected() -> None:
    """Backtester ORB produces expected entry (no observer dep)."""
    orders, fills = _run_backtester_orb()
    assert len(orders) == 1
    assert len(fills) == 1
    assert orders[0].instrument_id == "ESH1"
    assert orders[0].side == "BUY"
    assert orders[0].limit_price == EXPECTED_ENTRY_PRICE
    assert fills[0].fill_price == EXPECTED_ENTRY_PRICE
