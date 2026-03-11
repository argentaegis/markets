"""Integration tests for ORB 5m strategy (110)."""

from __future__ import annotations

from datetime import datetime, time, timezone
from pathlib import Path

import pytest

from src.domain.config import BacktestConfig
from src.engine.engine import run_backtest
from src.loader.config import DataProviderConfig
from src.loader.provider import LocalFileDataProvider
from src.domain.futures import FuturesContractSpec, TradingSession
from src.strategies.strategizer_adapter import StrategizerStrategy


FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "src" / "loader" / "tests" / "fixtures"


@pytest.fixture
def orb_provider_config() -> DataProviderConfig:
    """DataProviderConfig for ORB (1m bars)."""
    return DataProviderConfig(
        underlying_path=FIXTURES_ROOT / "underlying",
        options_path=FIXTURES_ROOT / "options",
        timeframes_supported=["1d", "1h", "1m"],
        missing_data_policy="RETURN_PARTIAL",
        max_quote_age=None,
    )


@pytest.fixture
def orb_config(orb_provider_config: DataProviderConfig) -> BacktestConfig:
    """BacktestConfig for ORB futures run (1m bars)."""
    session = TradingSession("RTH", time(9, 30), time(16, 0), "America/New_York")
    fc = FuturesContractSpec(symbol="ESH1", tick_size=0.25, point_value=50.0, session=session)
    return BacktestConfig(
        symbol="ESH1",
        start=datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, 16, 0, tzinfo=timezone.utc),
        timeframe_base="1m",
        data_provider_config=orb_provider_config,
        instrument_type="future",
        futures_contract_spec=fc,
    )


@pytest.mark.integration
def test_orb_5m_backtest_completes(orb_config: BacktestConfig, orb_provider_config: DataProviderConfig) -> None:
    """ORB backtest runs to completion with futures config (1m bars)."""
    provider = LocalFileDataProvider(orb_provider_config)
    strategy = StrategizerStrategy(
        "orb_5m",
        {"qty": 1, "min_range_ticks": 4, "max_range_ticks": 40},
        config=orb_config,
    )
    result = run_backtest(orb_config, strategy, provider)
    assert result.final_portfolio is not None
    assert result.config.instrument_type == "future"
    assert result.config.timeframe_base == "1m"


@pytest.mark.integration
def test_orb_5m_snapshot_has_futures_bars(orb_config: BacktestConfig, orb_provider_config: DataProviderConfig) -> None:
    """Engine populates futures_bars in snapshot for futures run."""
    from src.engine.engine import _build_step_snapshot

    provider = LocalFileDataProvider(orb_provider_config)
    ts = datetime(2026, 1, 2, 14, 35, tzinfo=timezone.utc)
    snapshot = _build_step_snapshot(
        provider,
        orb_config.symbol,
        orb_config.timeframe_base,
        ts,
        config=orb_config,
    )
    assert snapshot.futures_bars is not None
