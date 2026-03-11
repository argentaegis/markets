"""Massive options provider and converter via massive.RESTClient."""

from __future__ import annotations

import os
import warnings
from datetime import date, datetime, timezone
from typing import Any

from massive import RESTClient

from ..ticker import occ_ticker_to_contract_id

from .base import (
    OptionsChainConverter,
    OptionsChainProvider,
    OptionsQuotesConverter,
    OptionsQuotesProvider,
)


def _announce_mismatch(msg: str) -> None:
    warnings.warn(msg, stacklevel=2)


class MassiveOptionsChainProvider(OptionsChainProvider):
    """Fetch options chain from Massive via list_options_contracts (reference API)."""

    def __init__(self, api_key: str | None = None, pagination: bool = True) -> None:
        key = api_key or os.environ.get("MASSIVE_API_KEY") or os.environ.get("POLYGON_API_KEY")
        if not key:
            raise ValueError(
                "MASSIVE_API_KEY or POLYGON_API_KEY is required for options."
            )
        self._client = RESTClient(api_key=key, pagination=pagination)

    def get_chain_raw(
        self,
        underlying: str,
        expiration_date_gte: date,
        expiration_date_lte: date,
        *,
        strike_price_gte: float | None = None,
        strike_price_lte: float | None = None,
        limit: int | None = 1000,
    ) -> Any:
        """Fetch chain from reference/contracts API. Returns list of result dicts."""
        results = []
        cap = limit or 1000
        api_kwargs = {
            "underlying_ticker": underlying,
            "expiration_date_gte": expiration_date_gte,
            "expiration_date_lte": expiration_date_lte,
            "limit": min(cap, 1000),
        }
        if strike_price_gte is not None:
            api_kwargs["strike_price_gte"] = strike_price_gte
        if strike_price_lte is not None:
            api_kwargs["strike_price_lte"] = strike_price_lte
        for obj in self._client.list_options_contracts(**api_kwargs):
            results.append({
                "ticker": getattr(obj, "ticker", None),
                "underlying_ticker": getattr(obj, "underlying_ticker", None),
                "expiration_date": getattr(obj, "expiration_date", None),
                "strike_price": getattr(obj, "strike_price", None),
                "contract_type": getattr(obj, "contract_type", None),
                "shares_per_contract": getattr(obj, "shares_per_contract", None),
            })
            if len(results) >= cap:
                break  # Stop consuming iterator to avoid extra pagination requests
        return {"results": results}


class MassiveOptionsQuotesProvider(OptionsQuotesProvider):
    """Fetch historical options quotes from Massive via list_quotes."""

    def __init__(self, api_key: str | None = None, pagination: bool = True) -> None:
        key = api_key or os.environ.get("MASSIVE_API_KEY") or os.environ.get("POLYGON_API_KEY")
        if not key:
            raise ValueError(
                "MASSIVE_API_KEY or POLYGON_API_KEY is required for options."
            )
        self._client = RESTClient(api_key=key, pagination=pagination)

    def get_quotes_raw(self, options_ticker: str, start: date, end: date, limit: int | None = None) -> Any:
        """Fetch historical quotes. Returns list of raw quote dicts."""
        ticker = options_ticker if options_ticker.startswith("O:") else f"O:{options_ticker}"
        results = []
        for q in self._client.list_quotes(
            ticker=ticker,
            timestamp_gte=start.isoformat(),
            timestamp_lte=end.isoformat(),
            limit=limit or 50000,
        ):
            results.append(q)
        return {"results": results}


def _parse_chain_row(r: Any) -> dict | None:
    """Parse one raw chain result to metadata row. Returns None if skipped (no ticker/bad ticker)."""
    details = (r.get("details") or r) if isinstance(r, dict) else r
    if isinstance(details, dict):
        ticker = details.get("ticker")
        expiry_str = details.get("expiration_date")
        strike = float(details.get("strike_price") or 0)
        ctype = (details.get("contract_type") or "call").lower()
        mult = int(details.get("shares_per_contract") or 100)
    else:
        ticker = getattr(details, "ticker", None)
        expiry_str = getattr(details, "expiration_date", None)
        strike = float(getattr(details, "strike_price", 0) or 0)
        ctype = (getattr(details, "contract_type", None) or "call").lower()
        mult = int(getattr(details, "shares_per_contract", 100) or 100)
    if not ticker:
        return None
    try:
        contract_id = occ_ticker_to_contract_id(str(ticker))
    except ValueError:
        return None
    right = "C" if ctype == "call" else "P"
    underlying = contract_id.split("|")[0]
    if expiry_str:
        expiry = date.fromisoformat(str(expiry_str)[:10])
    else:
        expiry = date.fromisoformat(contract_id.split("|")[1])
    return {
        "underlying": underlying,
        "expiry": expiry,
        "strike": strike,
        "right": right,
        "contract_id": contract_id,
        "multiplier": float(mult),
    }


class MassiveOptionsChainConverter(OptionsChainConverter):
    """Convert Massive options chain to metadata rows. Supports reference API (flat) format."""

    def to_canonical(self, raw: Any) -> list[dict]:
        results = raw.get("results") or []
        rows = []
        skipped = 0
        for r in results:
            row = _parse_chain_row(r)
            if row is None:
                skipped += 1
            else:
                rows.append(row)
        if skipped:
            _announce_mismatch(f"Options chain: skipped {skipped} row(s) (missing/invalid ticker)")
        if len(rows) < len(results):
            _announce_mismatch(f"Options chain: {len(results)} raw -> {len(rows)} converted")
        return rows


class MassiveOptionsQuotesConverter(OptionsQuotesConverter):
    """Convert Massive quote results to (ts, bid, ask) series."""

    def to_canonical(self, raw: Any) -> list[tuple]:
        results = raw.get("results") or []
        rows = []
        skipped_ts = 0
        skipped_bid_ask = 0
        for r in results:
            ts_ns = r.get("sip_timestamp")
            if ts_ns is None:
                skipped_ts += 1
                continue
            bid = r.get("bid_price")
            ask = r.get("ask_price")
            if bid is None or ask is None:
                skipped_bid_ask += 1
                continue
            ts = datetime.fromtimestamp(ts_ns / 1e9, tz=timezone.utc)
            rows.append((ts, float(bid), float(ask)))
        if skipped_ts:
            _announce_mismatch(f"Options quotes: skipped {skipped_ts} row(s) with missing sip_timestamp")
        if skipped_bid_ask:
            _announce_mismatch(f"Options quotes: skipped {skipped_bid_ask} row(s) with missing bid/ask")
        if len(rows) < len(results):
            _announce_mismatch(f"Options quotes: {len(results)} raw -> {len(rows)} converted")
        return sorted(rows, key=lambda x: x[0])
