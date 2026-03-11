"""Fetch options chain and quotes from Massive. Shared by CLI and validation.

Writes metadata index + per-contract quote CSVs matching DataProvider Option B layout.
Rate limiting for Polygon free tier (5 req/min); MASSIVE_RATE_LIMIT=1 enables throttling.
"""

from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..config import CACHE_ROOT
from .sources.registry import (
    get_chain_converter,
    get_chain_provider,
    get_quotes_converter,
    get_quotes_provider,
)
from .ticker import contract_id_to_occ_ticker

# Polygon free tier: 5 requests/min. Enable via MASSIVE_RATE_LIMIT=1.
_INITIAL_WAIT_SEC = 65  # Ensures fresh rate-limit bucket before first request
_REQUEST_DELAY_SEC = 15  # ~4 req/min between subsequent requests


def _rate_limit_enabled() -> bool:
    v = os.environ.get("MASSIVE_RATE_LIMIT", "").strip().lower()
    return v in ("1", "true", "yes")


@dataclass
class FetchResult:
    metadata_count: int
    quotes_written: int
    out_dir: Path


def _access_error_msg(e: Exception, context: str = "options") -> str | None:
    err_msg = str(e)
    try:
        body = json.loads(err_msg) if err_msg.strip().startswith("{") else {}
    except json.JSONDecodeError:
        body = {}
    status = body.get("status", "")
    api_msg = body.get("message", "")
    if status == "NOT_AUTHORIZED" or "not entitled" in err_msg.lower():
        out = (
            f"Options {context} access denied: Polygon plan does not include options. "
            "See https://polygon.io/pricing"
        )
        return out + (f"\n  API: {api_msg}" if api_msg else out)
    if "429" in err_msg or "rate limit" in err_msg.lower():
        return (
            "Rate limit exceeded (Polygon free tier: 5 req/min). Fetch uses 1+ chain + 1 per quote. "
            "Wait 60s and retry, or use --max-contracts 10 --max-quotes 3."
        )
    return None


def _fetch_chain(
    chain_provider, chain_converter, underlying: str, start: date, end: date,
    max_contracts: int | None, strike_gte: float | None, strike_lte: float | None,
) -> list[dict]:
    """Fetch and convert chain. Raises RuntimeError on API access errors."""
    if _rate_limit_enabled():
        print("Waiting 65s for rate limit to reset (free tier: 5 req/min)...")
        time.sleep(_INITIAL_WAIT_SEC)
    try:
        raw_chain = chain_provider.get_chain_raw(
            underlying, start, end,
            limit=max_contracts,
            strike_price_gte=strike_gte,
            strike_price_lte=strike_lte,
        )
    except Exception as e:
        msg = _access_error_msg(e, "chain")
        if msg:
            raise RuntimeError(msg) from e
        raise
    metadata = chain_converter.to_canonical(raw_chain)
    if not metadata:
        raw_count = len(raw_chain.get("results") or [])
        raise RuntimeError(
            f"No option contracts in chain (API returned {raw_count} raw). "
            "Try a wider expiry range or check date format."
        )
    return metadata


def _write_metadata_index(meta_path: Path, metadata: list[dict]) -> None:
    """Write metadata index.csv."""
    with open(meta_path / "index.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["underlying", "expiry", "strike", "right", "contract_id", "multiplier"])
        w.writeheader()
        for row in metadata:
            w.writerow({**row, "expiry": row["expiry"].isoformat()})


def _fetch_and_write_quotes(
    quotes_provider, quotes_converter,
    metadata: list[dict], max_quotes: int | None, start: date, end: date,
    quotes_path: Path,
) -> int:
    """Fetch quotes for contracts, write CSVs. Returns count written."""
    to_fetch = metadata[:max_quotes] if max_quotes is not None else metadata
    written = 0
    for row in to_fetch:
        if _rate_limit_enabled():
            time.sleep(_REQUEST_DELAY_SEC)
        cid = row["contract_id"]
        try:
            occ = contract_id_to_occ_ticker(cid)
        except ValueError:
            continue
        try:
            raw_quotes = quotes_provider.get_quotes_raw(occ, start, end)
        except Exception as e:
            msg = _access_error_msg(e, "quotes")
            if msg:
                raise RuntimeError(msg) from e
            raise
        series = quotes_converter.to_canonical(raw_quotes)
        if series:
            with open(quotes_path / f"{cid}.csv", "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["quote_ts", "bid", "ask"])
                for ts, bid, ask in series:
                    w.writerow([ts.isoformat().replace("+00:00", "Z"), bid, ask])
            written += 1
    return written


def fetch_options(
    underlying: str,
    start: date,
    end: date,
    out_dir: Path | None = None,
    provider: str = "massive",
    max_contracts: int | None = None,
    max_quotes: int | None = None,
    strike_gte: float | None = None,
    strike_lte: float | None = None,
) -> FetchResult:
    """Fetch options chain and quotes, write to out_dir. Returns FetchResult or raises.

    Reasoning: index.csv + quotes/{contract_id}.csv layout matches loader expectation.
    max_contracts/max_quotes limit for free-tier; contract_id→OCC ticker for Polygon API.
    """
    underlying = underlying.upper()
    out_dir = out_dir or (CACHE_ROOT / provider / "options" / underlying.lower())
    pagination = not (max_contracts is not None or max_quotes is not None)
    chain_provider = get_chain_provider(provider, pagination=pagination)
    chain_converter = get_chain_converter(provider)
    quotes_provider = get_quotes_provider(provider, pagination=pagination)
    quotes_converter = get_quotes_converter(provider)

    metadata = _fetch_chain(
        chain_provider, chain_converter, underlying, start, end,
        max_contracts, strike_gte, strike_lte,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metadata").mkdir(parents=True, exist_ok=True)
    quotes_path = out_dir / "quotes"
    quotes_path.mkdir(parents=True, exist_ok=True)

    _write_metadata_index(out_dir / "metadata", metadata)
    written = _fetch_and_write_quotes(
        quotes_provider, quotes_converter,
        metadata, max_quotes, start, end, quotes_path,
    )
    return FetchResult(metadata_count=len(metadata), quotes_written=written, out_dir=out_dir)
