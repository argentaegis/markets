"""Integration test: export 2010 data produces 12 monthly files (done criteria)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from src.marketdata.underlying.export import export_split, filter_range
from src.marketdata.underlying.validate import validate_canonical


def _make_2010_bars() -> pd.DataFrame:
    """Synthetic SPX daily bars for 2010 — at least one trading day per month."""
    dates = [
        (1, 4), (1, 5), (1, 6),
        (2, 1), (2, 2), (2, 3),
        (3, 1), (3, 2), (3, 3),
        (4, 1), (4, 5), (4, 6),
        (5, 3), (5, 4), (5, 5),
        (6, 1), (6, 2), (6, 3),
        (7, 1), (7, 2), (7, 6),
        (8, 2), (8, 3), (8, 4),
        (9, 1), (9, 2), (9, 3),
        (10, 1), (10, 4), (10, 5),
        (11, 1), (11, 2), (11, 3),
        (12, 1), (12, 2), (12, 3),
    ]
    rows = []
    for i, (m, d) in enumerate(dates):
        v = 1100.0 + i * 0.5
        rows.append({
            "ts": datetime(2010, m, d, 21, 0, 0, tzinfo=timezone.utc),
            "open": v,
            "high": v + 2,
            "low": v - 2,
            "close": v + 1,
            "volume": 0,
        })
    return pd.DataFrame(rows)


def test_export_2010_creates_12_monthly_files(tmp_path: Path) -> None:
    """Done criteria: export 2010-01-01 to 2011-01-01 with split=month creates 12 files (parquet default)."""
    df = _make_2010_bars()
    filtered = filter_range(df, date(2010, 1, 1), date(2011, 1, 1))
    assert not filtered.empty
    validate_canonical(filtered)
    out_dir = tmp_path / "exports" / "spx" / "2010"
    paths = export_split(filtered, out_dir, "SPX", "month")
    assert len(paths) == 12
    for m in range(1, 13):
        p = out_dir / f"spx_2010_{m:02d}.parquet"
        assert p.exists(), f"Missing {p}"
