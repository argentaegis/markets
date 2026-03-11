"""Databento converter for manually-downloaded OHLCV CSV.

Converts XNAS (equities) and GLBX (futures) ohlcv-1m CSV to canonical format.
No API calls — user downloads from Databento portal; use md import-databento to ingest.
"""

from __future__ import annotations

from datetime import timezone
from typing import Any

import pandas as pd

from .base import FormatConverter


class DatabentoConverter(FormatConverter):
    """Convert Databento OHLCV CSV to canonical ts, open, high, low, close, volume."""

    def to_canonical(self, raw: Any) -> pd.DataFrame:
        """Convert Databento DataFrame to canonical format."""
        if not isinstance(raw, pd.DataFrame):
            return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
        df = raw
        if df.empty:
            return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
        required = ["ts_event", "open", "high", "low", "close", "volume"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(
                f"Databento CSV missing required columns: {missing}. "
                f"Expected: ts_event, open, high, low, close, volume, symbol"
            )
        result = df[required].copy()
        result = result.rename(columns={"ts_event": "ts"})
        result["ts"] = pd.to_datetime(result["ts"], utc=True)
        for col in ["open", "high", "low", "close", "volume"]:
            result[col] = result[col].astype(float)
        result = result.sort_values("ts").reset_index(drop=True)
        return result[["ts", "open", "high", "low", "close", "volume"]]
