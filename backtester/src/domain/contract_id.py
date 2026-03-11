"""Canonical contract_id format: {underlying}|{expiry}|{right}|{strike}|{multiplier}

Single canonical format for cross-module identity. Parser extracts format-defined
fields. Multiplier from metadata index is authoritative; parser does not infer multiplier
for P&L-critical use (different products vary).
"""

from __future__ import annotations

from datetime import date
from typing import NamedTuple
import re

FORMAT_SEP = "|"
FORMAT_PATTERN = re.compile(
    r"^([A-Za-z0-9.]+)\|(\d{4}-\d{2}-\d{2})\|([CP])\|([\d.]+)\|(\d+)$"
)


class ParsedContractId(NamedTuple):
    """Parsed contract_id fields. multiplier from format only; use metadata for authoritative value.

    Reasoning: NamedTuple gives named access without extra parsing. Multiplier in format
    for parse completeness; P&L uses metadata.multiplier (minis differ).
    """

    underlying: str
    expiry: date
    right: str
    strike: float
    multiplier: int  # from format; may not match index for minis, etc.


def format_contract_id(
    underlying: str,
    expiry: date,
    right: str,
    strike: float,
    multiplier: int = 100,
) -> str:
    """Format canonical contract_id. right is 'C' or 'P'."""
    parts = [underlying, expiry.isoformat(), right, str(strike), str(multiplier)]
    return FORMAT_SEP.join(parts)


def parse_contract_id(contract_id: str) -> ParsedContractId:
    """Parse canonical contract_id. Raises ValueError if invalid."""
    m = FORMAT_PATTERN.match(contract_id.strip())
    if not m:
        raise ValueError(f"Invalid contract_id format: {contract_id!r}")
    underlying, expiry_s, right, strike_s, mult_s = m.groups()
    return ParsedContractId(
        underlying=underlying,
        expiry=date.fromisoformat(expiry_s),
        right=right.upper(),
        strike=float(strike_s),
        multiplier=int(mult_s),
    )
