"""Phase 3.1: File loader tests."""

import pytest
from pathlib import Path

from src.loader.storage.file_loader import (
    load_metadata_index,
    load_option_quotes_series,
    load_underlying_bars,
)
from src.domain.bars import BarRow
from src.loader.tests.conftest import FIXTURES_ROOT


def test_load_underlying_csv() -> None:
    """FL1: Load underlying CSV; columns ts, open, high, low, close, volume."""
    path = FIXTURES_ROOT / "underlying" / "SPY_1d.csv"
    rows = load_underlying_bars(path)
    assert len(rows) > 0
    r = rows[0]
    assert isinstance(r, BarRow)
    assert hasattr(r, "ts") and hasattr(r, "open") and hasattr(r, "close")
    assert r.volume == 1000000


def test_load_underlying_parquet() -> None:
    """FL2: Load underlying parquet — same structure as CSV."""
    path = FIXTURES_ROOT / "underlying" / "SPY_1d.parquet"
    rows = load_underlying_bars(path)
    assert len(rows) > 0
    assert isinstance(rows[0], BarRow)
    assert rows[0].volume == 1000000


def test_load_metadata_index() -> None:
    """FL3: Load metadata index: underlying, expiry, strike, right → contract_id, multiplier."""
    path = FIXTURES_ROOT / "options" / "metadata" / "index.csv"
    meta = load_metadata_index(path)
    assert len(meta) > 0
    r = meta[0]
    assert "underlying" in r
    assert "expiry" in r
    assert "strike" in r
    assert "right" in r
    assert "contract_id" in r
    assert "multiplier" in r
    assert r["underlying"] == "SPY"


def test_load_option_quotes_series() -> None:
    """FL4: Load per-contract quote series (Option B)."""
    path = FIXTURES_ROOT / "options" / "quotes"
    # Use first contract_id from metadata
    contract_id = "SPY|2026-01-17|C|480|100"
    quote_path = path / f"{contract_id}.csv"
    series = load_option_quotes_series(quote_path)
    assert len(series) > 0
    t, bid, ask = series[0]
    assert bid == 5.10
    assert ask == 5.20


def test_load_returns_no_dataframe() -> None:
    """FL5: Raw load returns structured data, not DataFrame (domain objects at boundary)."""
    path = FIXTURES_ROOT / "underlying" / "SPY_1d.csv"
    rows = load_underlying_bars(path)
    assert isinstance(rows, list)
    assert all(isinstance(r, BarRow) for r in rows)
