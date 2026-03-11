"""Shared fixtures for DataProvider tests."""

from pathlib import Path
from datetime import datetime, timezone

from src.loader.provider import DataProviderConfig, LocalFileDataProvider

FIXTURES_ROOT = Path(__file__).parent / "fixtures"


def fixtures_underlying_path() -> Path:
    return FIXTURES_ROOT / "underlying"


def fixtures_options_path() -> Path:
    return FIXTURES_ROOT / "options"


def default_provider_config() -> DataProviderConfig:
    return DataProviderConfig(
        underlying_path=fixtures_underlying_path(),
        options_path=fixtures_options_path(),
        timeframes_supported=["1d", "1h", "1m"],
        missing_data_policy="RAISE",
        max_quote_age=60,
    )


def make_provider(**overrides) -> LocalFileDataProvider:
    config = default_provider_config()
    for k, v in overrides.items():
        setattr(config, k, v)
    return LocalFileDataProvider(config)


def utc(dt: datetime) -> datetime:
    """Ensure datetime is UTC-aware."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
