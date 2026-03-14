"""Predefined broker fee schedules. Per-instrument-type FeeModelConfig.

Broker fees vary by product: equity, option, future. Each broker has a schedule
keyed by instrument_type. Numbers are illustrative approximations; verify
against broker documentation for production use.
"""

from __future__ import annotations

from src.broker.fee_model import FeeModelConfig

# BrokerFeeSchedule: dict[str, FeeModelConfig] keyed by "equity" | "option" | "future"
BROKERS: dict[str, dict[str, FeeModelConfig]] = {
    "ibkr": {
        "equity": FeeModelConfig(per_contract=0.0, per_order=0.0, pct_of_notional=0.0),
        "option": FeeModelConfig(per_contract=0.65, per_order=1.0, pct_of_notional=0.0),
        "future": FeeModelConfig(per_contract=0.85, per_order=0.0, pct_of_notional=0.0),
    },
    "ibkr_equity_spread": {
        "equity": FeeModelConfig(per_contract=0.0, per_order=0.0, pct_of_notional=0.001),
        "option": FeeModelConfig(per_contract=0.65, per_order=1.0, pct_of_notional=0.0),
        "future": FeeModelConfig(per_contract=0.85, per_order=0.0, pct_of_notional=0.0),
    },
    "tdameritrade": {
        "equity": FeeModelConfig(per_contract=0.0, per_order=0.0, pct_of_notional=0.0),
        "option": FeeModelConfig(per_contract=0.65, per_order=0.50, pct_of_notional=0.0),
        "future": FeeModelConfig(per_contract=2.25, per_order=0.0, pct_of_notional=0.0),
    },
    "schwab": {
        "equity": FeeModelConfig(per_contract=0.0, per_order=0.0, pct_of_notional=0.0),
        "option": FeeModelConfig(per_contract=0.65, per_order=0.0, pct_of_notional=0.0),
        "future": FeeModelConfig(per_contract=2.25, per_order=0.0, pct_of_notional=0.0),
    },
    "zero": {
        "equity": FeeModelConfig(per_contract=0.0, per_order=0.0, pct_of_notional=0.0),
        "option": FeeModelConfig(per_contract=0.0, per_order=0.0, pct_of_notional=0.0),
        "future": FeeModelConfig(per_contract=0.0, per_order=0.0, pct_of_notional=0.0),
    },
}


def get_broker_schedule(broker_id: str) -> dict[str, FeeModelConfig]:
    """Return fee schedule for broker. Raises KeyError if broker unknown."""
    if broker_id not in BROKERS:
        raise KeyError(f"Unknown broker: {broker_id}. Available: {list(BROKERS.keys())}")
    return BROKERS[broker_id].copy()


def get_fee_config(broker_id: str, instrument_type: str) -> FeeModelConfig:
    """Return FeeModelConfig for broker + instrument_type."""
    schedule = get_broker_schedule(broker_id)
    if instrument_type not in schedule:
        raise KeyError(
            f"Broker {broker_id} has no schedule for instrument_type={instrument_type}"
        )
    return schedule[instrument_type]
