"""Broker: validate orders, FillModel, FeeModel, submit_orders → list[Fill].

Conforms to 000 M4, M5, M6. Pure functions; immutable.
"""

from __future__ import annotations

from src.broker.broker import submit_orders, validate_order
from src.broker.fee_model import FeeModelConfig, compute_fees
from src.broker.fill_model import FillModelConfig, fill_order

__all__ = [
    "compute_fees",
    "FeeModelConfig",
    "fill_order",
    "FillModelConfig",
    "submit_orders",
    "validate_order",
]
