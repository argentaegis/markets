"""File loader — reads parquet (primary) and CSV (legacy), returns structured data.

Standard format: parquet. Parquet/CSV columns: ts,open,high,low,close,volume for underlying;
options: quotes.parquet (contract_id, quote_ts, bid, ask) or quotes/{contract_id}.csv per contract;
metadata index: underlying,expiry,strike,right,contract_id,multiplier.

Underlying bars are loaded as DataFrames with a DatetimeIndex for fast slicing.
BarRow conversion happens only for the filtered result set.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import csv

import pandas as pd

from ...domain.bars import BarRow


def _parse_ts(s: str) -> datetime:
    """Parse ISO datetime; ensure UTC timezone-aware."""
    s = s.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_date(s: str) -> date:
    return date.fromisoformat(s.strip())


def _df_to_barrows(df: pd.DataFrame) -> list[BarRow]:
    """Convert a DataFrame slice to list of BarRow. Vectorized read, per-row construction."""
    rows: list[BarRow] = []
    ts_arr = df.index
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    volumes = df["volume"].values
    for i in range(len(df)):
        ts = ts_arr[i]
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        rows.append(BarRow(
            ts=ts,
            open=float(opens[i]),
            high=float(highs[i]),
            low=float(lows[i]),
            close=float(closes[i]),
            volume=float(volumes[i]),
        ))
    return rows


def load_underlying_bars_df(path: Path) -> pd.DataFrame | None:
    """Load underlying OHLCV into a DataFrame with DatetimeIndex on 'ts'.

    Returns None if path missing. Index is sorted and UTC-aware.
    """
    if not path.exists():
        return None
    if path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
    if df.empty:
        return None
    if not pd.api.types.is_datetime64_any_dtype(df["ts"]):
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
    elif df["ts"].dt.tz is None:
        df["ts"] = df["ts"].dt.tz_localize("UTC")
    df = df.set_index("ts").sort_index()
    return df


def load_underlying_bars(path: Path) -> list[BarRow]:
    """Load underlying OHLCV from parquet or CSV. Returns list of BarRow.

    Legacy interface kept for tests that expect list[BarRow].
    For performance, use load_underlying_bars_df + _df_to_barrows.
    """
    df = load_underlying_bars_df(path)
    if df is None or df.empty:
        return []
    return _df_to_barrows(df)


def load_metadata_index(path: Path) -> list[dict]:
    """Load metadata index: underlying, expiry, strike, right, contract_id, multiplier.

    Reasoning: Index enables get_option_chain filtering (symbol, expiry > ts) and
    get_contract_metadata lookup. Returns [] if path missing.
    """
    if not path.exists():
        return []
    result: list[dict] = []
    with open(path) as f:
        r = csv.DictReader(f)
        for line in r:
            row = {
                "underlying": line["underlying"],
                "expiry": _parse_date(line["expiry"]),
                "strike": float(line["strike"]),
                "right": line["right"].upper(),
                "contract_id": line["contract_id"],
                "multiplier": float(line["multiplier"]),
            }
            result.append(row)
    return result


def load_option_quotes_series(path: Path) -> list[tuple[datetime, float, float]]:
    """Load per-contract quote series from CSV. Returns [(quote_ts, bid, ask), ...] sorted by ts.

    For Parquet storage, use load_option_quotes_from_parquet instead.
    """
    if not path.exists():
        return []
    rows: list[tuple[datetime, float, float]] = []
    with open(path) as f:
        r = csv.DictReader(f)
        for line in r:
            ts = _parse_ts(line["quote_ts"])
            bid = float(line["bid"])
            ask = float(line["ask"])
            rows.append((ts, bid, ask))
    return sorted(rows, key=lambda x: x[0])


def _df_group_to_quote_series(
    grp: pd.DataFrame,
) -> list[tuple[datetime, float, float]]:
    """Convert a DataFrame group (contract's quotes) to [(ts, bid, ask), ...] sorted by ts."""
    rows: list[tuple[datetime, float, float]] = []
    for _, row in grp.iterrows():
        ts = row["quote_ts"]
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        rows.append((ts, float(row["bid"]), float(row["ask"])))
    return sorted(rows, key=lambda x: x[0])


def load_option_quotes_batch_from_parquet(
    path: Path, contract_ids: list[str]
) -> dict[str, list[tuple[datetime, float, float]]]:
    """Load quote series for many contracts in one parquet read (Plan 251a).

    Uses filters=[("contract_id", "in", contract_ids)] for predicate pushdown.
    Returns dict contract_id -> [(quote_ts, bid, ask), ...] sorted by ts.
    Contracts with no data are omitted from the result; caller should set cache[cid]=[].
    """
    if not path.exists() or not contract_ids:
        return {}
    df = pd.read_parquet(path, filters=[("contract_id", "in", contract_ids)])
    if df.empty:
        return {}
    result: dict[str, list[tuple[datetime, float, float]]] = {}
    for cid, grp in df.groupby("contract_id"):
        result[cid] = _df_group_to_quote_series(grp)
    return result


def load_option_quotes_from_parquet(
    path: Path, contract_id: str
) -> list[tuple[datetime, float, float]]:
    """Load quote series for one contract from consolidated quotes.parquet.

    Uses Parquet predicate pushdown to read only rows for the given contract_id.
    Returns [(quote_ts, bid, ask), ...] sorted by ts.
    For batch loading many contracts, use load_option_quotes_batch_from_parquet.
    """
    if not path.exists():
        return []
    df = pd.read_parquet(path, filters=[("contract_id", "==", contract_id)])
    if df.empty:
        return []
    return _df_group_to_quote_series(df)
