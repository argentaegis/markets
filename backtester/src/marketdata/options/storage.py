"""Options cache: Parquet + metadata. Export to CSV for DataProvider.

Layout: {provider}/options/{underlying}/metadata/index.csv, quotes/{contract_id}.csv.
Matches DataProvider paths. write_metadata/write_quotes_csv used by fetch; read_metadata
for validation/cache checks.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pandas as pd

from ..config import CACHE_ROOT


def _options_root(provider: str, underlying: str, cache_root: Path | None = None) -> Path:
    """Mirrors underlying: cache/{provider}/options/{symbol}/ (vs cache/{provider}/{interval}/{symbol}/)."""
    root = cache_root or CACHE_ROOT
    safe = underlying.replace("|", "_").replace(":", "_").lower()
    return root / provider / "options" / safe


def write_metadata(metadata: list[dict], provider: str, underlying: str, cache_root: Path | None = None) -> Path:
    """Write metadata index to CSV (for DataProvider).

    Reasoning: Column names match load_metadata_index expectation.
    """
    base = _options_root(provider, underlying, cache_root)
    meta_dir = base / "metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)
    path = meta_dir / "index.csv"
    if not metadata:
        path.touch()
        return path
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["underlying", "expiry", "strike", "right", "contract_id", "multiplier"])
        w.writeheader()
        for row in metadata:
            r = {**row, "expiry": row["expiry"].isoformat() if hasattr(row["expiry"], "isoformat") else row["expiry"]}
            w.writerow(r)
    return path


def write_quotes_csv(
    contract_id: str,
    series: list[tuple],
    provider: str,
    underlying: str,
    cache_root: Path | None = None,
) -> Path:
    """Write quote series to CSV (for DataProvider). series = [(ts, bid, ask), ...].

    Reasoning: quote_ts,bid,ask columns match load_option_quotes_series.
    """
    base = _options_root(provider, underlying, cache_root)
    quotes_dir = base / "quotes"
    quotes_dir.mkdir(parents=True, exist_ok=True)
    path = quotes_dir / f"{contract_id}.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["quote_ts", "bid", "ask"])
        for ts, bid, ask in series:
            ts_str = ts.isoformat().replace("+00:00", "Z") if hasattr(ts, "isoformat") else str(ts)
            w.writerow([ts_str, bid, ask])
    return path


def read_metadata(provider: str, underlying: str, cache_root: Path | None = None) -> list[dict] | None:
    """Read metadata index. Returns None if not found."""
    base = _options_root(provider, underlying, cache_root)
    path = base / "metadata" / "index.csv"
    if not path.exists():
        return None
    out = []
    with open(path) as f:
        r = csv.DictReader(f)
        for row in r:
            row["expiry"] = date.fromisoformat(row["expiry"])
            row["strike"] = float(row["strike"])
            row["multiplier"] = float(row["multiplier"])
            out.append(row)
    return out
