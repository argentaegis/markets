"""Massive provider and converter for indices/stocks OHLCV."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd

from massive import RESTClient

from .base import FormatConverter, MarketDataProvider

# Interval -> (multiplier, timespan) for Polygon aggregates API
_INTERVAL_MAP = {
    "1d": (1, "day"),
    "1h": (1, "hour"),
}


def _access_error_msg(e: Exception) -> str | None:
    """Return user-facing message for access/rate errors, or None to re-raise."""
    err_msg = str(e)
    try:
        body = json.loads(err_msg) if err_msg.strip().startswith("{") else {}
    except json.JSONDecodeError:
        body = {}
    status = body.get("status", "")
    api_msg = body.get("message", "")
    if status == "NOT_AUTHORIZED" or "not entitled" in err_msg.lower():
        out = "Underlying data access denied: check your Polygon.io API plan. See https://polygon.io/pricing"
        return out + (f"\n  API: {api_msg}" if api_msg else out)
    if "429" in err_msg or "rate limit" in err_msg.lower():
        return "Rate limit exceeded. Wait 60s and retry."
    return None


class MassiveProvider(MarketDataProvider):
    """Fetch OHLCV from Massive REST API via massive.RESTClient."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("MASSIVE_API_KEY") or os.environ.get("POLYGON_API_KEY")
        if not key:
            raise ValueError(
                "MASSIVE_API_KEY or POLYGON_API_KEY is required. Set the environment variable or pass api_key."
            )
        self._client = RESTClient(api_key=key)

    def get_ohlcv_raw(self, symbol: str, start: date, end: date, interval: str) -> Any:
        """Fetch raw bars. Returns dict with 'results' list (o, h, l, c, t, v)."""
        if interval not in _INTERVAL_MAP:
            raise ValueError(f"MassiveProvider supports {list(_INTERVAL_MAP)}; got {interval!r}")
        mult, timespan = _INTERVAL_MAP[interval]
        from_ = datetime(start.year, start.month, start.day, 0, 0, 0, tzinfo=timezone.utc)
        to_ = datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=timezone.utc)
        try:
            results = []
            for agg in self._client.list_aggs(
                ticker=symbol,
                multiplier=mult,
                timespan=timespan,
                from_=from_,
                to=to_,
            ):
                results.append({
                    "t": agg.timestamp,
                    "o": agg.open,
                    "h": agg.high,
                    "l": agg.low,
                    "c": agg.close,
                    "v": agg.volume if agg.volume is not None else 0,
                })
        except Exception as e:
            msg = _access_error_msg(e)
            if msg:
                raise RuntimeError(msg) from e
            raise
        return {"results": results, "ticker": symbol}


class MassiveConverter(FormatConverter):
    """Convert Massive API response to canonical ts, OHLCV."""

    def to_canonical(self, raw: Any) -> pd.DataFrame:
        results = raw.get("results") or []
        if not results:
            return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
        rows = []
        for r in results:
            # t is Unix millisecond timestamp
            ts = datetime.fromtimestamp(r["t"] / 1000, tz=timezone.utc)
            rows.append(
                {
                    "ts": ts,
                    "open": float(r["o"]),
                    "high": float(r["h"]),
                    "low": float(r["l"]),
                    "close": float(r["c"]),
                    "volume": float(r.get("v", 0)) if r.get("v") is not None else 0,
                }
            )
        df = pd.DataFrame(rows)
        return df.sort_values("ts").reset_index(drop=True)
