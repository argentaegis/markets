"""FeeModel: per-contract and per-order fees.

Conforms to 000 M6. Configurable via FeeModelConfig.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.fill import Fill
from src.domain.order import Order


@dataclass
class FeeModelConfig:
    """Per-contract commission and per-order fee."""

    per_contract: float
    per_order: float


def compute_fees(order: Order, fill: Fill, fee_config: FeeModelConfig) -> float:
    """Compute fees for a fill: per_contract * fill_qty + per_order."""
    return fee_config.per_contract * fill.fill_qty + fee_config.per_order
