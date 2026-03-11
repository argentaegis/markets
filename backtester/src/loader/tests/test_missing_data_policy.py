"""Phase 6.1: Missing data policy tests."""

from datetime import datetime, timezone
import pytest

from src.loader.tests.conftest import make_provider, utc


def test_raise_missing_bars() -> None:
    """MD1: RAISE: missing underlying bars in range → exception."""
    provider = make_provider()
    start = utc(datetime(2030, 1, 1, 21, 0, 0))
    end = utc(datetime(2030, 1, 1, 21, 0, 0))
    with pytest.raises(Exception, match="No bars|Missing"):
        provider.get_underlying_bars("SPY", "1d", start, end)


def test_raise_stale_quote() -> None:
    """MD2: RAISE: stale quote → exception."""
    provider = make_provider()
    ts = utc(datetime(2026, 1, 5, 14, 30, 0))
    with pytest.raises(Exception, match="stale|MissingData"):
        provider.get_option_quotes(["SPY|2026-01-10|C|490|10"], ts)


def test_return_empty() -> None:
    """MD3: RETURN_EMPTY: missing data → empty / None."""
    provider = make_provider(missing_data_policy="RETURN_EMPTY")
    c = provider.get_contract_metadata("SPY|9999-01-01|C|999|100")
    assert c is None


def test_return_partial() -> None:
    """MD4: RETURN_PARTIAL: partial data with flags."""
    provider = make_provider(missing_data_policy="RETURN_PARTIAL")
    c = provider.get_contract_metadata("SPY|2026-06-19|C|500|100")
    assert c is not None
    assert c.underlying_symbol == "SPY"


def test_policy_uniform() -> None:
    """MD5: Policy applied uniformly across methods."""
    # RETURN_EMPTY: bars returns empty, metadata returns None
    provider = make_provider(missing_data_policy="RETURN_EMPTY")
    start = utc(datetime(2030, 1, 1, 21, 0, 0))
    end = utc(datetime(2030, 1, 1, 21, 0, 0))
    bars = provider.get_underlying_bars("SPY", "1d", start, end)
    assert len(bars.rows) == 0
