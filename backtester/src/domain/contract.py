"""ContractSpec — immutable metadata for an option contract.

Frozen so specs cannot be mutated after fetch/storage. metadata_missing flags partial
data when source returned RETURN_PARTIAL.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ContractSpec:
    """Immutable metadata for one option contract.

    Reasoning: strike/expiry/right used for filtering and P&L; multiplier critical for
    contract value (options vs minis differ). metadata_missing=True when not in index.
    """

    contract_id: str
    underlying_symbol: str
    strike: float
    expiry: date
    right: str  # "C" or "P"
    multiplier: float
    metadata_missing: bool = False  # True when from RETURN_PARTIAL (not in index)
