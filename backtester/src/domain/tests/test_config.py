"""BacktestConfig domain object tests.

Reasoning: All runs driven by typed BacktestConfig. Config is
saved with run artifacts. Determinism requires config + seed + data to be
reproducible. Config must be serializable for run_manifest.json.
"""

from __future__ import annotations

import json
from datetime import datetime, time, timezone
from pathlib import Path

import pytest

from src.broker.fill_model import FillModelConfig
from src.domain.config import BacktestConfig
from src.domain.futures import FuturesContractSpec, TradingSession
from src.loader.provider import DataProviderConfig


def test_config_create_minimal(sample_symbol: str) -> None:
    """BC1: Create BacktestConfig with symbol, start, end, timeframe_base.

    Reasoning: Clock and DataProvider need these to drive the simulation.
    Without symbol and date range, we cannot fetch data or iterate timestamps.
    """
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
    dp_config = DataProviderConfig(
        underlying_path=Path("/fixtures/underlying"),
        options_path=Path("/fixtures/options"),
    )
    config = BacktestConfig(
        symbol=sample_symbol,
        start=start,
        end=end,
        timeframe_base="1d",
        data_provider_config=dp_config,
        broker="zero",
    )
    assert config.symbol == sample_symbol
    assert config.start == start
    assert config.end == end
    assert config.timeframe_base == "1d"


def test_config_seed_optional(sample_symbol: str) -> None:
    """BC2: seed is int or None; None = no stochastic.

    Reasoning: Deterministic runs use fixed seed. None means
    no stochastic behavior (e.g. no mid-improvement probability in FillModel).
    """
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
    dp_config = DataProviderConfig(
        underlying_path=Path("/f"),
        options_path=Path("/o"),
    )
    config_no_seed = BacktestConfig(
        symbol=sample_symbol,
        start=start,
        end=end,
        timeframe_base="1d",
        data_provider_config=dp_config,
        broker="zero",
    )
    assert config_no_seed.seed is None

    config_with_seed = BacktestConfig(
        symbol=sample_symbol,
        start=start,
        end=end,
        timeframe_base="1d",
        data_provider_config=dp_config,
        broker="zero",
        seed=42,
    )
    assert config_with_seed.seed == 42


def test_config_data_provider_config(sample_symbol: str) -> None:
    """BC3: data_provider_config references DataProviderConfig or paths.

    Reasoning: BacktestConfig drives the run; it must tell the engine where
    to load data. DataProviderConfig (from loader) already has underlying_path,
    options_path, missing_data_policy, etc.
    """
    dp_config = DataProviderConfig(
        underlying_path=Path("/data/underlying"),
        options_path=Path("/data/options"),
    )
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
    config = BacktestConfig(
        symbol=sample_symbol,
        start=start,
        end=end,
        timeframe_base="1d",
        data_provider_config=dp_config,
        broker="zero",
    )
    assert config.data_provider_config == dp_config
    assert str(config.data_provider_config.underlying_path) == "/data/underlying"


def test_config_serializable(sample_symbol: str) -> None:
    """BC4: Config is serializable (to dict, to JSON).

    Reasoning: Config is saved with run artifacts. run_manifest.json
    must include run params for reproducibility. to_dict() enables JSON dump.
    """
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
    dp_config = DataProviderConfig(
        underlying_path=Path("/f"),
        options_path=Path("/o"),
    )
    config = BacktestConfig(
        symbol=sample_symbol,
        start=start,
        end=end,
        timeframe_base="1d",
        data_provider_config=dp_config,
        broker="zero",
        seed=42,
    )
    d = config.to_dict()
    assert isinstance(d, dict)
    assert d["symbol"] == sample_symbol
    assert d["timeframe_base"] == "1d"
    assert d["seed"] == 42
    # Must be JSON-serializable (no Path objects as-is; they become str)
    json.dumps(d)  # must not raise


def test_config_roundtrip(sample_symbol: str) -> None:
    """BC5: Round-trip — config -> dict -> config reproduces same run params.

    Reasoning: Determinism requires that loading a saved config yields
    the same run. Round-trip test catches serialization bugs (e.g. datetime
    format, Path handling).
    """
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
    dp_config = DataProviderConfig(
        underlying_path=Path("/fixtures/underlying"),
        options_path=Path("/fixtures/options"),
    )
    original = BacktestConfig(
        symbol=sample_symbol,
        start=start,
        end=end,
        timeframe_base="1h",
        data_provider_config=dp_config,
        broker="zero",
        seed=123,
    )
    d = original.to_dict()
    restored = BacktestConfig.from_dict(d)
    assert restored.symbol == original.symbol
    assert restored.start == original.start
    assert restored.end == original.end
    assert restored.timeframe_base == original.timeframe_base
    assert restored.seed == original.seed


def test_config_timeframe_mvp_values(sample_symbol: str) -> None:
    """BC6: timeframe_base in ["1d", "1h", "1m"].

    Reasoning: MVP supports these bar sizes. Clock and DataProvider
    are built for them.
    """
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
    dp_config = DataProviderConfig(
        underlying_path=Path("/f"),
        options_path=Path("/o"),
    )
    for tf in ["1d", "1h", "1m"]:
        config = BacktestConfig(
            symbol=sample_symbol,
            start=start,
            end=end,
            timeframe_base=tf,
            data_provider_config=dp_config,
            broker="zero",
        )
        assert config.timeframe_base == tf


# --- Phase 3 (070): BacktestConfig engine extensions ---


def test_config_initial_cash_default(sample_symbol: str) -> None:
    """BC7: initial_cash defaults to 100_000.0.

    Reasoning: Engine needs starting cash for PortfolioState. Default covers
    most backtesting scenarios without requiring explicit config.
    """
    dp = DataProviderConfig(underlying_path=Path("/f"), options_path=Path("/o"))
    config = BacktestConfig(
        symbol=sample_symbol,
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        timeframe_base="1d",
        data_provider_config=dp,
        broker="zero",
    )
    assert config.initial_cash == 100_000.0


def test_config_initial_cash_custom(sample_symbol: str) -> None:
    """BC8: initial_cash can be set to custom value."""
    dp = DataProviderConfig(underlying_path=Path("/f"), options_path=Path("/o"))
    config = BacktestConfig(
        symbol=sample_symbol,
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        timeframe_base="1d",
        data_provider_config=dp,
        broker="zero",
        initial_cash=50_000.0,
    )
    assert config.initial_cash == 50_000.0


def test_config_fill_config_defaults_none(sample_symbol: str) -> None:
    """BC9: fill_config defaults to None (default spread)."""
    dp = DataProviderConfig(underlying_path=Path("/f"), options_path=Path("/o"))
    config = BacktestConfig(
        symbol=sample_symbol,
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        timeframe_base="1d",
        data_provider_config=dp,
        broker="zero",
    )
    assert config.fill_config is None


def test_config_broker_and_fill_config(sample_symbol: str) -> None:
    """BC10: broker and fill_config accept values."""
    dp = DataProviderConfig(underlying_path=Path("/f"), options_path=Path("/o"))
    fill = FillModelConfig(synthetic_spread_bps=100.0)
    config = BacktestConfig(
        symbol=sample_symbol,
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        timeframe_base="1d",
        data_provider_config=dp,
        broker="tdameritrade",
        fill_config=fill,
    )
    assert config.broker == "tdameritrade"
    assert config.fill_config.synthetic_spread_bps == 100.0


def test_config_to_dict_includes_engine_fields(sample_symbol: str) -> None:
    """BC11: to_dict includes initial_cash, broker, fill_config."""
    dp = DataProviderConfig(underlying_path=Path("/f"), options_path=Path("/o"))
    fill = FillModelConfig(synthetic_spread_bps=100.0)
    config = BacktestConfig(
        symbol=sample_symbol,
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        timeframe_base="1d",
        data_provider_config=dp,
        broker="ibkr",
        initial_cash=50_000.0,
        fill_config=fill,
    )
    d = config.to_dict()
    assert d["initial_cash"] == 50_000.0
    assert d["broker"] == "ibkr"
    assert d["fill_config"]["synthetic_spread_bps"] == 100.0
    json.dumps(d)  # must be JSON-serializable


def test_config_roundtrip_engine_fields(sample_symbol: str) -> None:
    """BC12: Round-trip preserves initial_cash, broker, fill_config."""
    dp = DataProviderConfig(underlying_path=Path("/f"), options_path=Path("/o"))
    fill = FillModelConfig(synthetic_spread_bps=100.0)
    original = BacktestConfig(
        symbol=sample_symbol,
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        timeframe_base="1d",
        data_provider_config=dp,
        broker="tdameritrade",
        initial_cash=50_000.0,
        fill_config=fill,
        seed=42,
    )
    restored = BacktestConfig.from_dict(original.to_dict())
    assert restored.initial_cash == 50_000.0
    assert restored.broker == "tdameritrade"
    assert restored.fill_config is not None
    assert restored.fill_config.synthetic_spread_bps == 100.0


def test_config_roundtrip_engine_fields_none(sample_symbol: str) -> None:
    """BC13: Round-trip when fill_config is None."""
    dp = DataProviderConfig(underlying_path=Path("/f"), options_path=Path("/o"))
    original = BacktestConfig(
        symbol=sample_symbol,
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        timeframe_base="1d",
        data_provider_config=dp,
        broker="zero",
    )
    restored = BacktestConfig.from_dict(original.to_dict())
    assert restored.initial_cash == 100_000.0
    assert restored.broker == "zero"
    assert restored.fill_config is None


def test_config_roundtrip_fill_timing(sample_symbol: str) -> None:
    """BC15: Round-trip preserves fill_timing (Plan 265)."""
    dp = DataProviderConfig(underlying_path=Path("/f"), options_path=Path("/o"))
    for fill_timing in ["same_bar_close", "next_bar_open"]:
        original = BacktestConfig(
            symbol=sample_symbol,
            start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end=datetime(2026, 1, 31, tzinfo=timezone.utc),
            timeframe_base="1d",
            data_provider_config=dp,
            broker="zero",
            fill_timing=fill_timing,
        )
        restored = BacktestConfig.from_dict(original.to_dict())
        assert restored.fill_timing == fill_timing


def test_config_fill_timing_default(sample_symbol: str) -> None:
    """BC16: fill_timing defaults to next_bar_open (Plan 278 — safe-by-default against lookahead)."""
    dp = DataProviderConfig(underlying_path=Path("/f"), options_path=Path("/o"))
    config = BacktestConfig(
        symbol=sample_symbol,
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        timeframe_base="1d",
        data_provider_config=dp,
        broker="zero",
    )
    assert config.fill_timing == "next_bar_open"


def test_config_roundtrip_futures(sample_symbol: str) -> None:
    """BC14: Round-trip preserves instrument_type and futures_contract_spec (070)."""
    dp = DataProviderConfig(underlying_path=Path("/f"), options_path=Path("/o"))
    session = TradingSession(
        name="RTH",
        start_time=time(9, 30),
        end_time=time(16, 0),
        timezone="America/New_York",
    )
    fc = FuturesContractSpec(symbol="ESH26", tick_size=0.25, point_value=50.0, session=session)
    original = BacktestConfig(
        symbol="ESH26",
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        timeframe_base="1d",
        data_provider_config=dp,
        broker="zero",
        instrument_type="future",
        futures_contract_spec=fc,
    )
    restored = BacktestConfig.from_dict(original.to_dict())
    assert restored.instrument_type == "future"
    assert restored.futures_contract_spec is not None
    assert restored.futures_contract_spec.symbol == "ESH26"
    assert restored.futures_contract_spec.point_value == 50.0


def test_config_roundtrip_option_chain_fields(sample_symbol: str) -> None:
    """BC17: Round-trip preserves option_contract_ids, option_chain_sigma_limit, option_chain_vol_default (Plan 266)."""
    dp = DataProviderConfig(underlying_path=Path("/f"), options_path=Path("/o"))
    original = BacktestConfig(
        symbol=sample_symbol,
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        timeframe_base="1d",
        data_provider_config=dp,
        broker="zero",
        option_contract_ids=["SPY|2026-01-17|C|480|100"],
        option_chain_sigma_limit=2.0,
        option_chain_vol_default=0.20,
    )
    restored = BacktestConfig.from_dict(original.to_dict())
    assert restored.option_contract_ids == ["SPY|2026-01-17|C|480|100"]
    assert restored.option_chain_sigma_limit == 2.0
    assert restored.option_chain_vol_default == 0.20


def test_config_option_chain_sigma_limit_none(sample_symbol: str) -> None:
    """BC18: option_chain_sigma_limit can be None (disables filter)."""
    dp = DataProviderConfig(underlying_path=Path("/f"), options_path=Path("/o"))
    original = BacktestConfig(
        symbol=sample_symbol,
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        timeframe_base="1d",
        data_provider_config=dp,
        broker="zero",
        option_chain_sigma_limit=None,
    )
    restored = BacktestConfig.from_dict(original.to_dict())
    assert restored.option_chain_sigma_limit is None
