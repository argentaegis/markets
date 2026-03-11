"""Integration tests for trailing stop (Plan 150)."""

from __future__ import annotations

from datetime import datetime, time, timezone
from pathlib import Path

import pytest

from src.domain.config import BacktestConfig
from src.domain.futures import FuturesContractSpec, TradingSession
from src.engine.engine import run_backtest
from src.loader.config import DataProviderConfig
from src.loader.provider import LocalFileDataProvider
from src.strategies.strategizer_adapter import StrategizerStrategy


FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "src" / "loader" / "tests" / "fixtures"

CONFIGS_DIR = Path(__file__).resolve().parents[1] / "configs"


TRAILING_UNDERLYING = FIXTURES_ROOT / "underlying_trailing"  # ESH1_1m triggers MA cross


@pytest.fixture
def trailing_provider_config() -> DataProviderConfig:
    """DataProviderConfig for trailing stop (1m bars)."""
    return DataProviderConfig(
        underlying_path=TRAILING_UNDERLYING,
        options_path=FIXTURES_ROOT / "options",
        timeframes_supported=["1d", "1h", "1m"],
        missing_data_policy="RETURN_PARTIAL",
        max_quote_age=None,
    )


@pytest.fixture
def trailing_config(trailing_provider_config: DataProviderConfig) -> BacktestConfig:
    """BacktestConfig for trend_entry_trailing_stop futures run."""
    session = TradingSession("RTH", time(9, 30), time(16, 0), "America/New_York")
    fc = FuturesContractSpec(symbol="ESH1", tick_size=0.25, point_value=50.0, session=session)
    return BacktestConfig(
        symbol="ESH1",
        start=datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, 16, 0, tzinfo=timezone.utc),
        timeframe_base="1m",
        data_provider_config=trailing_provider_config,
        instrument_type="future",
        futures_contract_spec=fc,
        initial_cash=500_000.0,  # ESH26 at 5412 needs ~270k per contract
    )


@pytest.mark.integration
def test_trend_entry_trailing_stop_backtest_completes(
    trailing_config: BacktestConfig,
    trailing_provider_config: DataProviderConfig,
) -> None:
    """trend_entry_trailing_stop backtest runs; strategizer enters step 1, trailing stop exits step 2."""
    provider = LocalFileDataProvider(trailing_provider_config)
    strategy = StrategizerStrategy(
        "trend_entry_trailing_stop",
        {"qty": 1, "trailing_stop_ticks": 4, "ma_period": 1},  # ma_period=1: 2 bars needed; fixture has 3 1m bars
        config=trailing_config,
    )
    result = run_backtest(trailing_config, strategy, provider)

    assert result.final_portfolio is not None
    assert len(result.fills) == 2  # Entry + trailing exit
    assert len(result.orders) == 2  # Entry order + synthetic trailing order
    assert "ESH1" not in result.final_portfolio.positions
    assert any("trailing-" in o.id for o in result.orders)


@pytest.mark.integration
def test_trailing_stop_cli(tmp_path: Path) -> None:
    """CLI runs trend_entry_trailing_stop config."""
    from src.runner import run_backtest_cli

    config_path = CONFIGS_DIR / "trend_entry_trailing_stop.yaml"
    run_dir = run_backtest_cli(config_path, tmp_path / "output")
    assert (run_dir / "summary.json").exists()
    summary = __import__("json").loads((run_dir / "summary.json").read_text())
    assert summary["num_trades"] >= 1


@pytest.mark.integration
def test_trend_follow_risk_sized_backtest_completes(
    trailing_config: BacktestConfig,
    trailing_provider_config: DataProviderConfig,
) -> None:
    """trend_follow_risk_sized backtest runs; portfolio-aware sizing, no re-entry."""
    provider = LocalFileDataProvider(trailing_provider_config)
    strategy = StrategizerStrategy(
        "trend_follow_risk_sized",
        {
            "ma_period": 1,
            "trailing_stop_ticks": 4,
            "risk_pct": 0.01,
            "max_qty": 5,
        },
        config=trailing_config,
    )
    result = run_backtest(trailing_config, strategy, provider)

    assert result.final_portfolio is not None
    assert len(result.fills) == 2
    assert len(result.orders) == 2
    assert "ESH1" not in result.final_portfolio.positions
