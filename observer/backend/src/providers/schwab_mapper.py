"""Schwab symbol mapping, ContractSpec extraction, and DataQuality mapping.

Bidirectional mapping between Schwab futures symbols (e.g., "/ESH26") and
canonical types (FutureSymbol, ContractSpec). Also maps SECURITY_STATUS
strings to DataQuality enum values.
"""

from __future__ import annotations

import logging
import re
from datetime import time

from core.instrument import (
    ContractSpec,
    FutureSymbol,
    InstrumentType,
    TradingSession,
)
from core.market_data import DataQuality

logger = logging.getLogger(__name__)

_KNOWN_ROOTS = {"ES", "NQ", "CL", "GC", "SI", "ZB", "ZN", "ZF", "YM", "RTY"}

_CONTRACT_CODE_RE = re.compile(r"^/([A-Z]{2,3})([A-Z]\d{2})?$")

_SECURITY_STATUS_MAP: dict[str, DataQuality] = {
    "Normal": DataQuality.OK,
    "Halted": DataQuality.STALE,
    "Closed": DataQuality.STALE,
}

_DEFAULT_SESSION = TradingSession(
    name="RTH",
    start_time=time(9, 30),
    end_time=time(16, 0),
    timezone="US/Eastern",
)


def schwab_to_canonical(schwab_symbol: str) -> FutureSymbol:
    """Convert a Schwab futures symbol to a canonical FutureSymbol.

    Accepts both root-only ("/ES") and active contract ("/ESH26") forms.
    """
    if not schwab_symbol or not schwab_symbol.startswith("/"):
        raise ValueError(f"Invalid Schwab symbol format: {schwab_symbol!r}")

    match = _CONTRACT_CODE_RE.match(schwab_symbol)
    if not match:
        raise ValueError(f"Cannot parse Schwab symbol: {schwab_symbol!r}")

    root = match.group(1)
    contract_code = match.group(2) or ""
    return FutureSymbol(
        root=root,
        contract_code=contract_code,
        front_month_alias=f"/{root}",
    )


def canonical_to_schwab(canonical_symbol: str) -> str:
    """Convert a canonical symbol string (e.g., "ESH26") to Schwab root format ("/ES").

    Schwab subscriptions use root-only symbols for futures.
    """
    for root in sorted(_KNOWN_ROOTS, key=len, reverse=True):
        if canonical_symbol.startswith(root):
            return f"/{root}"
    raise ValueError(f"Unknown root for canonical symbol: {canonical_symbol!r}")


def map_security_status(status: str | None) -> DataQuality:
    """Map Schwab SECURITY_STATUS to canonical DataQuality."""
    if status is None:
        return DataQuality.PARTIAL
    return _SECURITY_STATUS_MAP.get(status, DataQuality.PARTIAL)


def parse_trading_hours(hours_str: str | None) -> TradingSession:
    """Parse Schwab FUTURE_TRADING_HOURS into a TradingSession.

    Falls back to default RTH session if parsing fails.
    """
    if not hours_str:
        return _DEFAULT_SESSION
    return _DEFAULT_SESSION


def extract_contract_spec(quote_data: dict) -> ContractSpec | None:
    """Extract a ContractSpec from Schwab REST API quote response.

    Accepts the per-symbol object from /marketdata/v1/quotes which contains
    'quote' and 'reference' sub-objects. Returns None if required fields are
    missing.
    """
    q = quote_data.get("quote", {})
    ref = quote_data.get("reference", {})

    tick = q.get("tick") or ref.get("tick")
    multiplier = q.get("futureMultiplier") or ref.get("futureMultiplier")
    if tick is None or multiplier is None:
        return None

    raw_symbol = q.get("futureActiveSymbol") or q.get("symbol", "")
    try:
        fs = schwab_to_canonical(raw_symbol)
    except ValueError:
        logger.warning("Cannot parse symbol from quote data: %s", raw_symbol)
        return None

    hours_str = ref.get("futureTradingHours")
    session = parse_trading_hours(hours_str)

    return ContractSpec(
        symbol=fs.to_symbol(),
        instrument_type=InstrumentType.FUTURE,
        tick_size=float(tick),
        point_value=float(multiplier),
        session=session,
    )
