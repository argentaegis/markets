"""Split and write Parquet or CSV."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd


def filter_range(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Filter [start, end) — inclusive start, exclusive end."""
    df = df.copy()
    df["_date"] = pd.to_datetime(df["ts"]).dt.date
    out = df[(df["_date"] >= start) & (df["_date"] < end)].drop(columns=["_date"])
    return out.reset_index(drop=True)


def export_split(
    df: pd.DataFrame,
    out_dir: Path,
    symbol: str,
    split: str,
    format: str = "parquet",
) -> list[Path]:
    """Export by split mode. Returns list of written paths. Default format: parquet."""
    out_dir.mkdir(parents=True, exist_ok=True)
    df = df.copy()
    ts = pd.to_datetime(df["ts"])
    df["_year"] = ts.dt.year
    df["_month"] = ts.dt.month
    df["_quarter"] = (df["_month"] - 1) // 3 + 1
    written: list[Path] = []
    sym_lower = symbol.replace("|", "_").replace(":", "_").lower()
    ext = ".parquet" if format == "parquet" else ".csv"
    if split == "none":
        path = out_dir / f"{sym_lower}{ext}"
        _write_df(df.drop(columns=["_year", "_month", "_quarter"]), path, format)
        written.append(path)
        return written
    if split == "month":
        for (y, m), g in df.groupby(["_year", "_month"]):
            path = out_dir / f"{sym_lower}_{y}_{m:02d}{ext}"
            _write_df(g.drop(columns=["_year", "_month", "_quarter"]), path, format)
            written.append(path)
    elif split == "quarter":
        for (y, q), g in df.groupby(["_year", "_quarter"]):
            path = out_dir / f"{sym_lower}_{y}_q{q}{ext}"
            _write_df(g.drop(columns=["_year", "_month", "_quarter"]), path, format)
            written.append(path)
    elif split == "year":
        for y, g in df.groupby("_year"):
            path = out_dir / f"{sym_lower}_{y}{ext}"
            _write_df(g.drop(columns=["_year", "_month", "_quarter"]), path, format)
            written.append(path)
    return written


def _write_df(df: pd.DataFrame, path: Path, format: str) -> None:
    df = df.copy()
    if format == "parquet":
        df.to_parquet(path, index=False)
    else:
        df["ts"] = pd.to_datetime(df["ts"]).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        df.to_csv(path, index=False, columns=["ts", "open", "high", "low", "close", "volume"])
