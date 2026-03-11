"""Hard/soft validation for OHLCV data."""

from __future__ import annotations

from typing import Any

import pandas as pd


REQUIRED_COLUMNS = ["ts", "open", "high", "low", "close", "volume"]


class ValidationError(Exception):
    """Raised when hard validation fails."""

    pass


def validate_canonical(df: pd.DataFrame) -> list[str]:
    """Run hard checks. Raises ValidationError on failure. Returns list of soft warnings."""
    if df.empty:
        raise ValidationError("DataFrame is empty")
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            raise ValidationError(f"Missing required column: {col}")
    if df["ts"].duplicated().any():
        raise ValidationError("Duplicate timestamps")
    sorted_df = df.sort_values("ts").reset_index(drop=True)
    diffs = sorted_df["ts"].diff().dropna()
    if len(diffs) > 0 and (diffs <= pd.Timedelta(0)).any():
        raise ValidationError("Timestamps must be strictly increasing")
    for _, row in df.iterrows():
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        if h < max(o, c) or l > min(o, c) or l > h:
            raise ValidationError(f"OHLC sanity failed: o={o} h={h} l={l} c={c}")
    warnings: list[str] = []
    if "volume" in df.columns and (df["volume"].isna().all() or (df["volume"] == 0).all()):
        warnings.append("Volume missing or all zeros (expected for indices)")
    return warnings
