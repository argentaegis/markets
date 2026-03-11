"""Continuous futures series — stitch multiple contracts into one front-month series.

Roll rule: at each timestamp, use the bar from the contract with the nearest
unexpired expiry (3rd Friday of contract month for ES/NQ style).
"""

from __future__ import annotations

import calendar
import re
from datetime import date
from typing import Any

import pandas as pd

MONTH_CODE = {"H": 3, "M": 6, "U": 9, "Z": 12}  # ES/NQ: Mar, Jun, Sep, Dec


def _third_friday(year: int, month: int) -> date:
    """Third Friday of month (ES futures expiry)."""
    c = calendar.Calendar(firstweekday=calendar.MONDAY)
    monthcal = c.monthdatescalendar(year, month)
    fridays = [
        day
        for week in monthcal
        for day in week
        if day.weekday() == 4 and day.month == month
    ]
    return fridays[2]


def _expiry_from_symbol(symbol: str) -> date | None:
    """Parse expiry date from futures symbol like ESH1, ESM6, NQZ2."""
    m = re.match(r"^[A-Z]{2}([HMUZ])(\d)$", str(symbol))
    if not m:
        return None
    month_code, year_digit = m.group(1), int(m.group(2))
    month = MONTH_CODE.get(month_code)
    if month is None:
        return None
    year = 2020 + year_digit  # 1=2021, 2=2022, ..., 6=2026
    return _third_friday(year, month)


def build_continuous_series(
    df: pd.DataFrame,
    *,
    root: str = "ES",
) -> pd.DataFrame:
    """Build front-month continuous series from multi-contract futures DataFrame.

    Args:
        df: Databento-style DataFrame with columns ts_event, symbol, open, high, low, close, volume.
        root: Root symbol prefix (ES, NQ, etc.) to filter contracts.

    Returns:
        Canonical DataFrame (ts, open, high, low, close, volume) with one row per timestamp.
    """
    if df.empty or "symbol" not in df.columns or "ts_event" not in df.columns:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])

    single_contracts = [
        s for s in df["symbol"].unique()
        if isinstance(s, str)
        and s.startswith(root)
        and "-" not in s
        and _expiry_from_symbol(s) is not None
    ]
    if not single_contracts:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])

    sub = df[df["symbol"].isin(single_contracts)].copy()
    sub["ts"] = pd.to_datetime(sub["ts_event"], utc=True)
    sub["date"] = sub["ts"].dt.date

    expiry_map = {s: _expiry_from_symbol(s) for s in single_contracts}
    sub["expiry"] = sub["symbol"].map(expiry_map)
    sub = sub[sub["expiry"].notna()].copy()
    sub = sub[sub["expiry"] >= sub["date"]].copy()
    if sub.empty:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])

    idx = sub.groupby("ts")["expiry"].idxmin()
    out = sub.loc[idx, ["ts", "open", "high", "low", "close", "volume"]].copy()
    out = out.sort_values("ts").reset_index(drop=True)
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = out[col].astype(float)
    return out
