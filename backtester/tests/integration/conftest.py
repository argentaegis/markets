"""Shared fixtures for project-level integration tests.

Strategizer runs in-process (no HTTP service). strategizer_required is a no-op.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.loader.provider import DataProviderConfig, LocalFileDataProvider

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "src" / "loader" / "tests" / "fixtures"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register custom flags for integration tests."""
    parser.addoption(
        "--save-reports",
        action="store_true",
        default=False,
        help="Write reporter integration test output to test_runs/ instead of tmp_path",
    )
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Regenerate golden test files in tests/golden/ from current run output",
    )


@pytest.fixture
def fixtures_root() -> Path:
    """Path to src/loader/tests/fixtures."""
    return FIXTURES_ROOT


@pytest.fixture
def provider_config(fixtures_root: Path) -> DataProviderConfig:
    """DataProviderConfig with RETURN_PARTIAL, max_quote_age=None (matches validation behavior)."""
    return DataProviderConfig(
        underlying_path=fixtures_root / "underlying",
        options_path=fixtures_root / "options",
        timeframes_supported=["1d", "1h", "1m"],
        missing_data_policy="RETURN_PARTIAL",
        max_quote_age=None,
    )


@pytest.fixture
def provider(provider_config: DataProviderConfig) -> LocalFileDataProvider:
    """LocalFileDataProvider configured for integration tests."""
    return LocalFileDataProvider(provider_config)


@pytest.fixture
def report_output_dir(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    """Output directory for reporter tests.

    Default: tmp_path (ephemeral). With --save-reports: test_runs/{test_name}/
    in project root (persistent, one directory per test, no overwrites).
    """
    if request.config.getoption("--save-reports"):
        test_name = request.node.name
        out = PROJECT_ROOT / "test_runs" / test_name
        out.mkdir(parents=True, exist_ok=True)
        return out
    return tmp_path


@pytest.fixture(autouse=True)
def load_dotenv_for_integration() -> None:
    """Load .env for network-dependent tests (underlying, options) that need MASSIVE_API_KEY."""
    from dotenv import load_dotenv

    load_dotenv(override=True)


@pytest.fixture
def strategizer_required() -> None:
    """No-op: strategizer runs in-process (no HTTP service required)."""
