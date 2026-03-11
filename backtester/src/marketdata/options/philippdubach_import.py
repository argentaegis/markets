"""Import philippdubach/options-dataset-hist Parquet into backtester options layout.

Reads Parquet from data/cache/philippdubach/parquet_spy/, converts OCC contract_id
to canonical format, writes metadata/index.csv and quotes.parquet (single file).

Source: https://github.com/philippdubach/options-dataset-hist
Data is daily EOD; quote_ts uses market close (21:00 UTC).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def _occ_to_contract_id_vectorized(df: pd.DataFrame) -> pd.Series:
    """Convert OCC ticker column to contract_id. Returns Series; invalid -> NaN."""
    occ = df["contract_id"].astype(str).str.strip()
    occ = occ.str.removeprefix("O:")
    # Format: SYMBOL + YYMMDD + C/P + 8-digit strike
    m = occ.str.extract(r"^([A-Z0-9.]+)(\d{6})([CP])(\d{8})$", expand=True)
    m.columns = ["underlying", "yymmdd", "right", "strike_padded"]
    valid = m["underlying"].notna()
    yy = pd.to_numeric(m["yymmdd"].str[:2], errors="coerce")
    mm = pd.to_numeric(m["yymmdd"].str[2:4], errors="coerce")
    dd = pd.to_numeric(m["yymmdd"].str[4:6], errors="coerce")
    strike = pd.to_numeric(m["strike_padded"], errors="coerce") / 1000
    year = (2000 + yy).where(yy < 50, 1900 + yy)
    yr = year.fillna(2000).astype(int)
    mo = mm.fillna(1).astype(int)
    dy = dd.fillna(1).astype(int)
    expiry = yr.astype(str) + "-" + mo.astype(str).str.zfill(2) + "-" + dy.astype(str).str.zfill(2)
    result = pd.Series(index=df.index, dtype="object")
    result[valid] = (
        m["underlying"].str.upper() + "|" + expiry + "|" +
        m["right"].str.upper() + "|" + strike.astype("int").astype(str) + "|100"
    )
    return result


def import_philippdubach(
    cache_dir: Path,
    out_dir: Path,
    symbol: str = "SPY",
    start_year: int = 2021,
    end_year: int = 2025,
    quote_ts_hour_utc: int = 21,
) -> dict[str, Any]:
    """Import philippdubach Parquet into backtester options layout.

    Args:
        cache_dir: Directory containing options_YYYY.parquet files.
        out_dir: Output directory (metadata/, quotes/ created here).
        symbol: Filter by underlying symbol (default SPY).
        start_year: First year to include (inclusive).
        end_year: Last year to include (inclusive).
        quote_ts_hour_utc: Hour for quote_ts (default 21 = 4pm ET).

    Returns:
        Dict with metadata_count, quotes_rows, out_dir.
    """
    symbol = symbol.upper()
    metadata_path = out_dir / "metadata" / "index.csv"
    quotes_parquet_path = out_dir / "quotes.parquet"

    dfs: list[pd.DataFrame] = []
    for year in range(start_year, end_year + 1):
        parquet_file = cache_dir / f"options_{year}.parquet"
        if not parquet_file.exists():
            continue
        df = pd.read_parquet(parquet_file)
        if df.empty:
            continue
        if "symbol" in df.columns:
            df = df[df["symbol"] == symbol].copy()
        if df.empty:
            continue
        dfs.append(df)

    if not dfs:
        return {"metadata_count": 0, "quotes_rows": 0, "out_dir": str(out_dir)}

    combined = pd.concat(dfs, ignore_index=True)

    # Convert OCC to contract_id
    combined["contract_id"] = _occ_to_contract_id_vectorized(combined)
    combined = combined[combined["contract_id"].notna()].copy()

    # Filter valid quotes: at least one of bid/ask > 0
    bid = pd.to_numeric(combined["bid"], errors="coerce").fillna(0)
    ask = pd.to_numeric(combined["ask"], errors="coerce").fillna(0)
    valid_quote = (bid > 0) | (ask > 0)
    combined = combined[valid_quote].copy()
    bid = bid[valid_quote]
    ask = ask[valid_quote]
    combined["bid"] = bid.where(bid > 0, ask)
    combined["ask"] = ask.where(ask > 0, bid)

    # quote_ts as datetime
    date_str = combined["date"].astype(str).str.strip().str[:10]
    valid_dates = date_str.str.len() >= 10
    combined = combined[valid_dates].copy()
    combined["quote_ts"] = pd.to_datetime(
        date_str[valid_dates] + f"T{quote_ts_hour_utc:02d}:00:00Z",
        utc=True,
    )

    # Build metadata: unique contracts
    meta_df = combined[["contract_id", "symbol", "expiration", "strike", "type"]].drop_duplicates(
        subset=["contract_id"], keep="first"
    )
    meta_df["underlying"] = meta_df["symbol"].fillna(symbol).str.upper()
    meta_df["expiry"] = meta_df["expiration"].astype(str).str[:10]
    meta_df["right"] = meta_df["type"].fillna("C").astype(str).str.upper().str[0]
    meta_df["right"] = meta_df["right"].where(meta_df["right"].isin(["C", "P"]), "C")
    meta_df["multiplier"] = 100

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    meta_df[["underlying", "expiry", "strike", "right", "contract_id", "multiplier"]].to_csv(
        metadata_path, index=False
    )

    # Write single quotes.parquet
    quotes_df = combined[["contract_id", "quote_ts", "bid", "ask"]].sort_values(
        ["contract_id", "quote_ts"]
    )
    quotes_df.to_parquet(quotes_parquet_path, index=False)

    return {
        "metadata_count": len(meta_df),
        "quotes_rows": len(quotes_df),
        "out_dir": str(out_dir),
    }
