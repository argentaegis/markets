"""Tests for broker fee schedules."""

from __future__ import annotations

import pytest

from src.broker.fee_schedules import BROKERS, get_broker_schedule, get_fee_config


def test_get_broker_schedule_returns_schedule() -> None:
    """get_broker_schedule returns dict with equity, option, future."""
    schedule = get_broker_schedule("ibkr")
    assert "equity" in schedule
    assert "option" in schedule
    assert "future" in schedule
    assert len(schedule) == 3


def test_get_fee_config_per_instrument_type() -> None:
    """get_fee_config returns correct FeeModelConfig per instrument type."""
    opt = get_fee_config("tdameritrade", "option")
    assert opt.per_contract == 0.65
    assert opt.per_order == 0.50

    eq = get_fee_config("ibkr", "equity")
    assert eq.per_contract == 0.0
    assert eq.per_order == 0.0

    fut = get_fee_config("ibkr", "future")
    assert fut.per_contract == 0.85
    assert fut.per_order == 0.0


def test_zero_broker_all_zeros() -> None:
    """zero broker has zero fees for all instrument types."""
    for itype in ("equity", "option", "future"):
        cfg = get_fee_config("zero", itype)
        assert cfg.per_contract == 0.0
        assert cfg.per_order == 0.0
        assert cfg.pct_of_notional == 0.0


def test_unknown_broker_raises() -> None:
    """Unknown broker raises KeyError."""
    with pytest.raises(KeyError, match="Unknown broker"):
        get_broker_schedule("nonexistent")


def test_ibkr_equity_spread_has_pct_of_notional() -> None:
    """ibkr_equity_spread has 10 bps for equity."""
    cfg = get_fee_config("ibkr_equity_spread", "equity")
    assert cfg.pct_of_notional == 0.001
