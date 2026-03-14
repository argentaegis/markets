"""FeeModel: per-contract, per-order, and pct-of-notional fees.

Conforms to 000 M6. Configurable via FeeModelConfig.
Plan 265: pct_of_notional for equity spread/slippage cost (basis-point style).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.fill import Fill
from src.domain.order import Order


@dataclass
class FeeModelConfig:
    """Per-contract commission, per-order fee, and optional pct-of-notional.

    pct_of_notional: decimal fraction (e.g. 0.001 = 10 bps round-trip).
    Used for equity spread/slippage cost; composes with per_contract + per_order.
    """

    per_contract: float
    per_order: float
    pct_of_notional: float = 0.0


def compute_fees(
    order: Order,
    fill: Fill,
    fee_config: FeeModelConfig,
    *,
    multiplier: float = 1.0,
) -> float:
    """Compute fees for a fill: per_contract * fill_qty + per_order + pct_of_notional * notional."""
    base = fee_config.per_contract * fill.fill_qty + fee_config.per_order
    if fee_config.pct_of_notional <= 0:
        return base
    notional = abs(fill.fill_price * fill.fill_qty * multiplier)
    return base + fee_config.pct_of_notional * notional
