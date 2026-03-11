"""Read/write cache + metadata."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import CACHE_ROOT


def cache_path(
    provider: str,
    symbol: str,
    interval: str,
    start: date,
    end: date,
    cache_root: Path | None = None,
) -> Path:
    """Path for parquet file. symbol normalized (lowercase, no special chars for path)."""
    root = cache_root or CACHE_ROOT
    safe = symbol.replace("|", "_").replace(":", "_").lower()
    return root / provider / "underlying" / interval / safe / f"bars_{start.isoformat()}_{end.isoformat()}.parquet"


def write_cache(
    df: pd.DataFrame,
    provider: str,
    user_symbol: str,
    provider_symbol: str,
    interval: str,
    start: date,
    end: date,
    source: str = "",
    cache_root: Path | None = None,
) -> Path:
    """Write canonical DataFrame to Parquet and metadata sidecar."""
    path = cache_path(provider, user_symbol, interval, start, end, cache_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    meta = {
        "provider": provider,
        "user_symbol": user_symbol,
        "provider_symbol": provider_symbol,
        "interval": interval,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "notes": "",
    }
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    return path


def read_cache(
    provider: str,
    symbol: str,
    interval: str,
    start: date,
    end: date,
    cache_root: Path | None = None,
) -> pd.DataFrame | None:
    """Read cached Parquet. Returns None if not found."""
    path = cache_path(provider, symbol, interval, start, end, cache_root)
    if not path.exists():
        return None
    return pd.read_parquet(path)
