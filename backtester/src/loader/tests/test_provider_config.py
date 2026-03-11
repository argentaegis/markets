"""Phase 2.2: DataProviderConfig tests."""

from pathlib import Path

from src.loader.provider import DataProviderConfig
from src.loader.tests.conftest import default_provider_config, fixtures_underlying_path, fixtures_options_path


def test_config_has_paths() -> None:
    """CF1: Config has underlying_path, options_path."""
    c = default_provider_config()
    assert c.underlying_path == fixtures_underlying_path()
    assert c.options_path == fixtures_options_path()


def test_config_missing_data_policy() -> None:
    """CF2: Config has missing_data_policy; default RAISE."""
    c = DataProviderConfig(underlying_path="/x", options_path="/y")
    assert c.missing_data_policy == "RAISE"


def test_config_max_quote_age() -> None:
    """CF3: Config has max_quote_age."""
    c = default_provider_config()
    assert c.get_max_quote_age_seconds() == 60.0


def test_config_timeframes_supported() -> None:
    """CF4: Config has timeframes_supported."""
    c = default_provider_config()
    assert "1d" in c.timeframes_supported
    assert "1h" in c.timeframes_supported
    assert "1m" in c.timeframes_supported


def test_config_serializable() -> None:
    """CF5: Config is serializable for run manifest."""
    c = default_provider_config()
    d = c.to_dict()
    assert "underlying_path" in d
    assert "options_path" in d
    assert "missing_data_policy" in d
    assert "max_quote_age" in d
    assert "timeframes_supported" in d
