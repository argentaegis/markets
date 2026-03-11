"""Phase 7.2: Run manifest tests."""

from datetime import datetime, timezone

from src.loader.tests.conftest import default_provider_config, make_provider, utc


def test_config_saved_in_manifest() -> None:
    """RM1, RM2: DataProvider config serializable; includes key params."""
    c = default_provider_config()
    d = c.to_dict()
    assert "underlying_path" in d
    assert "options_path" in d
    assert "timeframes_supported" in d
    assert "missing_data_policy" in d
    assert "max_quote_age" in d


def test_run_manifest_includes_crossed_quote_count() -> None:
    """Reporter/diagnostics: crossed_quotes_sanitized tracked in run manifest."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 2, 14, 33, 0))
    provider.get_option_quotes(["SPY|2026-01-17|C|480|100"], ts)  # crossed at 14:33
    manifest = provider.get_run_manifest_data()
    assert "diagnostics" in manifest
    assert "crossed_quotes_sanitized" in manifest["diagnostics"]
    assert manifest["diagnostics"]["crossed_quotes_sanitized"] >= 1
