"""OCC ticker <-> canonical contract_id conversion."""

from __future__ import annotations

import re
from datetime import date


def occ_ticker_to_contract_id(ticker: str) -> str:
    """Convert OCC-style ticker to contract_id. E.g. O:SPY250117C00480000 -> SPY|2026-01-17|C|480|100."""
    t = ticker.strip()
    if t.startswith("O:"):
        t = t[2:]
    # Format: SYMBOL + YYMMDD + C/P + 8-digit strike
    m = re.match(r"^([A-Z0-9.]+)(\d{6})([CP])(\d{8})$", t, re.IGNORECASE)
    if not m:
        raise ValueError(f"Invalid OCC ticker: {ticker!r}")
    underlying, yymmdd, right, strike_padded = m.groups()
    yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
    year = 2000 + yy if yy < 50 else 1900 + yy
    expiry = date(year, mm, dd)
    strike = int(strike_padded) / 1000.0
    return f"{underlying.upper()}|{expiry.isoformat()}|{right.upper()}|{strike:.0f}|100"


def contract_id_to_occ_ticker(contract_id: str) -> str:
    """Convert contract_id to OCC-style ticker. E.g. SPY|2026-01-17|C|480|100 -> O:SPY250117C00480000."""
    parts = contract_id.split("|")
    if len(parts) != 5:
        raise ValueError(f"Invalid contract_id: {contract_id!r}")
    underlying, expiry_str, right, strike_str, mult_str = parts
    expiry = date.fromisoformat(expiry_str)
    strike = float(strike_str)
    yymmdd = expiry.strftime("%y%m%d")
    strike_padded = f"{int(strike * 1000):08d}"
    return f"O:{underlying}{yymmdd}{right.upper()[0]}{strike_padded}"
