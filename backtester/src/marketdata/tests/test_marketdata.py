"""Tests for marketdata converter, validate, export."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import tempfile

import pandas as pd
import pytest

from src.marketdata.underlying.sources.continuous_futures import build_continuous_series
from src.marketdata.underlying.sources.massive_underlying import MassiveConverter
from src.marketdata.underlying.export import export_split, filter_range
from src.marketdata.underlying.storage import cache_path, read_cache, write_cache
from src.marketdata.underlying.validate import ValidationError, validate_canonical


def test_continuous_futures_roll() -> None:
    """Continuous series picks front-month contract (nearest unexpired expiry)."""
    df = pd.DataFrame({
        "ts_event": [
            "2021-03-01T00:00:00Z", "2021-03-01T00:00:00Z",  # ESH1 and ESM1 same ts
            "2021-03-20T00:00:00Z",  # after ESH1 expiry (Mar 19), ESM1 only
        ],
        "symbol": ["ESH1", "ESM1", "ESM1"],
        "open": [3800.0, 3790.0, 3860.0],
        "high": [3810.0, 3800.0, 3870.0],
        "low": [3795.0, 3785.0, 3855.0],
        "close": [3805.0, 3795.0, 3865.0],
        "volume": [100.0, 50.0, 90.0],
    })
    out = build_continuous_series(df, root="ES")
    assert len(out) == 2
    assert out.iloc[0]["close"] == 3805.0  # ESH1 (front month on Mar 1)
    assert out.iloc[1]["close"] == 3865.0  # ESM1 (only contract after ESH1 expiry)


def test_massive_converter_empty() -> None:
    conv = MassiveConverter()
    df = conv.to_canonical({"results": []})
    assert df.empty
    assert list(df.columns) == ["ts", "open", "high", "low", "close", "volume"]


def test_massive_converter() -> None:
    conv = MassiveConverter()
    raw = {
        "results": [
            {"t": 1291237200000, "o": 1200.0, "h": 1210.0, "l": 1195.0, "c": 1205.0, "v": 1e6},
            {"t": 1291323600000, "o": 1205.0, "h": 1220.0, "l": 1200.0, "c": 1215.0},
        ],
        "ticker": "I:SPX",
    }
    df = conv.to_canonical(raw)
    assert len(df) == 2
    assert df.columns.tolist() == ["ts", "open", "high", "low", "close", "volume"]
    assert df.iloc[0]["open"] == 1200.0
    assert df.iloc[0]["volume"] == 1e6
    assert df.iloc[1]["volume"] == 0  # missing v
    assert df.iloc[0]["ts"].tzinfo is not None


def test_validate_ok() -> None:
    utc = timezone.utc
    df = pd.DataFrame({
        "ts": [
            datetime(2010, 1, 4, 21, 0, 0, tzinfo=utc),
            datetime(2010, 1, 5, 21, 0, 0, tzinfo=utc),
        ],
        "open": [100.0, 101.0],
        "high": [102.0, 103.0],
        "low": [99.0, 100.0],
        "close": [101.0, 102.0],
        "volume": [1000.0, 1100.0],
    })
    warnings = validate_canonical(df)
    assert isinstance(warnings, list)


def test_validate_duplicate_ts() -> None:
    df = pd.DataFrame({
        "ts": [datetime(2010, 1, 4, 21, 0, 0, tzinfo=timezone.utc)] * 2,
        "open": [100.0, 100.0],
        "high": [102.0, 102.0],
        "low": [99.0, 99.0],
        "close": [101.0, 101.0],
        "volume": [1000.0, 1000.0],
    })
    with pytest.raises(ValidationError, match="Duplicate"):
        validate_canonical(df)


def test_validate_ohlc_sanity() -> None:
    df = pd.DataFrame({
        "ts": [datetime(2010, 1, 4, 21, 0, 0, tzinfo=timezone.utc)],
        "open": [100.0],
        "high": [95.0],  # high < close
        "low": [99.0],
        "close": [101.0],
        "volume": [1000.0],
    })
    with pytest.raises(ValidationError, match="OHLC"):
        validate_canonical(df)


def test_filter_range() -> None:
    df = pd.DataFrame({
        "ts": [
            datetime(2010, 1, 4, 21, 0, 0, tzinfo=timezone.utc),
            datetime(2010, 1, 5, 21, 0, 0, tzinfo=timezone.utc),
            datetime(2010, 2, 1, 21, 0, 0, tzinfo=timezone.utc),
        ],
        "open": [100.0] * 3,
        "high": [102.0] * 3,
        "low": [99.0] * 3,
        "close": [101.0] * 3,
        "volume": [1000.0] * 3,
    })
    out = filter_range(df, date(2010, 1, 5), date(2010, 2, 1))
    assert len(out) == 1
    out = filter_range(df, date(2010, 1, 1), date(2010, 2, 1))
    assert len(out) == 2
    out = filter_range(df, date(2010, 1, 1), date(2011, 1, 1))
    assert len(out) == 3


def test_export_split_month_parquet() -> None:
    df = pd.DataFrame({
        "ts": [
            datetime(2010, 1, 4, 21, 0, 0, tzinfo=timezone.utc),
            datetime(2010, 1, 5, 21, 0, 0, tzinfo=timezone.utc),
            datetime(2010, 2, 1, 21, 0, 0, tzinfo=timezone.utc),
        ],
        "open": [100.0] * 3,
        "high": [102.0] * 3,
        "low": [99.0] * 3,
        "close": [101.0] * 3,
        "volume": [1000.0] * 3,
    })
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        paths = export_split(df, out, "SPX", "month", format="parquet")
        assert len(paths) == 2
        assert (out / "spx_2010_01.parquet").exists()
        assert (out / "spx_2010_02.parquet").exists()


def test_export_split_month_csv() -> None:
    df = pd.DataFrame({
        "ts": [
            datetime(2010, 1, 4, 21, 0, 0, tzinfo=timezone.utc),
            datetime(2010, 1, 5, 21, 0, 0, tzinfo=timezone.utc),
            datetime(2010, 2, 1, 21, 0, 0, tzinfo=timezone.utc),
        ],
        "open": [100.0] * 3,
        "high": [102.0] * 3,
        "low": [99.0] * 3,
        "close": [101.0] * 3,
        "volume": [1000.0] * 3,
    })
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        paths = export_split(df, out, "SPX", "month", format="csv")
        assert len(paths) == 2
        assert (out / "spx_2010_01.csv").exists()
        content = (out / "spx_2010_01.csv").read_text()
        assert "ts,open,high,low,close,volume" in content


def test_storage_roundtrip() -> None:
    df = pd.DataFrame({
        "ts": [datetime(2010, 1, 4, 21, 0, 0, tzinfo=timezone.utc)],
        "open": [100.0],
        "high": [102.0],
        "low": [99.0],
        "close": [101.0],
        "volume": [1000.0],
    })
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = write_cache(
            df,
            provider="massive",
            user_symbol="SPX",
            provider_symbol="I:SPX",
            interval="1d",
            start=date(2010, 1, 1),
            end=date(2010, 1, 31),
            cache_root=root,
        )
        assert path.exists()
        assert path.with_suffix(path.suffix + ".meta.json").exists()
        back = read_cache("massive", "SPX", "1d", date(2010, 1, 1), date(2010, 1, 31), cache_root=root)
        assert back is not None
        assert len(back) == 1
        assert back.iloc[0]["close"] == 101.0
