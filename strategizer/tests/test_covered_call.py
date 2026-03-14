"""Tests for CoveredCall strategy (Plan 267)."""

from __future__ import annotations

from datetime import datetime, timezone

from strategizer.strategies.covered_call import CoveredCallStrategy
from strategizer.types import BarInput, Signal


class _MockPortfolio:
    def __init__(self, positions: dict[str, object]) -> None:
        self._positions = positions

    def get_positions(self) -> dict[str, object]:
        return self._positions

    def get_cash(self) -> float:
        return 100_000.0

    def get_equity(self) -> float:
        return 100_000.0


def _pv(instrument_id: str, qty: int, avg_price: float = 0.0) -> object:
    return type("PV", (), {"instrument_id": instrument_id, "qty": qty, "avg_price": avg_price})()


def test_covered_call_emits_buy_shares_when_insufficient() -> None:
    """When shares < shares_per_contract, emit BUY for shares."""
    strat = CoveredCallStrategy()
    ts = datetime(2026, 1, 2, 14, 35, tzinfo=timezone.utc)
    portfolio = _MockPortfolio({})
    signals = strat.evaluate(
        ts=ts,
        bars_by_symbol={"SPY": {"1d": [_bar(480.0)]}},
        specs={},
        portfolio=portfolio,
        step_index=1,
        strategy_params={"symbol": "SPY", "shares_per_contract": 100},
        option_chain=[],
    )
    assert len(signals) == 1
    assert signals[0].direction == "LONG"
    assert signals[0].qty == 100
    assert signals[0].symbol == "SPY"


def test_covered_call_emits_sell_call_when_shares_and_no_short() -> None:
    """When shares >= 100 and no short call, emit SELL call."""
    strat = CoveredCallStrategy()
    ts = datetime(2026, 1, 2, 14, 35, tzinfo=timezone.utc)
    portfolio = _MockPortfolio({"SPY": _pv("SPY", 100, 480.0)})
    chain = ["SPY|2026-01-17|C|480|100", "SPY|2026-02-21|C|490|100"]
    signals = strat.evaluate(
        ts=ts,
        bars_by_symbol={"SPY": {"1d": [_bar(481.0)]}},
        specs={},
        portfolio=portfolio,
        step_index=2,
        strategy_params={"symbol": "SPY", "shares_per_contract": 100, "strike_rule": "atm", "dte_target": 30},
        option_chain=chain,
    )
    assert len(signals) == 1
    assert signals[0].direction == "SHORT"
    assert signals[0].qty == 1
    assert signals[0].instrument_id in chain


def test_covered_call_emits_nothing_when_short_call_present() -> None:
    """When short call exists, do not emit sell (wait for expiry)."""
    strat = CoveredCallStrategy()
    ts = datetime(2026, 1, 2, 14, 35, tzinfo=timezone.utc)
    portfolio = _MockPortfolio({
        "SPY": _pv("SPY", 100, 480.0),
        "SPY|2026-01-17|C|480|100": _pv("SPY|2026-01-17|C|480|100", -1, 5.0),
    })
    chain = ["SPY|2026-01-17|C|480|100"]
    signals = strat.evaluate(
        ts=ts,
        bars_by_symbol={"SPY": {"1d": [_bar(481.0)]}},
        specs={},
        portfolio=portfolio,
        step_index=3,
        strategy_params={"symbol": "SPY", "shares_per_contract": 100},
        option_chain=chain,
    )
    assert len(signals) == 0


def test_covered_call_uses_contract_id_fallback_when_chain_empty() -> None:
    """When option_chain empty but contract_id in params, use contract_id."""
    strat = CoveredCallStrategy()
    ts = datetime(2026, 1, 2, 14, 35, tzinfo=timezone.utc)
    portfolio = _MockPortfolio({"SPY": _pv("SPY", 100, 480.0)})
    contract_id = "SPY|2026-01-17|C|480|100"
    signals = strat.evaluate(
        ts=ts,
        bars_by_symbol={"SPY": {"1d": [_bar(481.0)]}},
        specs={},
        portfolio=portfolio,
        step_index=2,
        strategy_params={"symbol": "SPY", "shares_per_contract": 100, "contract_id": contract_id},
        option_chain=[],
    )
    assert len(signals) == 1
    assert signals[0].instrument_id == contract_id
    assert signals[0].direction == "SHORT"


def test_covered_call_option_fetch_spec_holding_short_returns_contract_ids() -> None:
    """When holding short call, option_fetch_spec returns that contract only."""
    strat = CoveredCallStrategy()
    ts = datetime(2026, 1, 2, 14, 35, tzinfo=timezone.utc)
    portfolio = _MockPortfolio({
        "SPY": _pv("SPY", 100, 480.0),
        "SPY|2026-01-17|C|480|100": _pv("SPY|2026-01-17|C|480|100", -1, 5.0),
    })
    spec = strat.option_fetch_spec(ts, portfolio, 480.0, 3, {"symbol": "SPY"})
    assert spec is not None
    assert spec.contract_ids == ["SPY|2026-01-17|C|480|100"]
    assert spec.sigma_limit is None


def test_covered_call_option_fetch_spec_no_short_returns_sigma_limit() -> None:
    """When no short call, option_fetch_spec returns sigma_limit for chain selection."""
    strat = CoveredCallStrategy()
    ts = datetime(2026, 1, 2, 14, 35, tzinfo=timezone.utc)
    portfolio = _MockPortfolio({"SPY": _pv("SPY", 100, 480.0)})
    spec = strat.option_fetch_spec(ts, portfolio, 480.0, 2, {"symbol": "SPY"})
    assert spec is not None
    assert spec.contract_ids is None
    assert spec.sigma_limit == 2.0


def _bar(close: float) -> BarInput:
    return BarInput(
        ts=datetime(2026, 1, 2, 14, 35, tzinfo=timezone.utc),
        open=close - 1.0,
        high=close + 1.0,
        low=close - 2.0,
        close=close,
        volume=1_000_000.0,
    )
