"""Tests for PortfolioView, ContractSpecView, Requirements."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import time

import pytest

from strategizer.protocol import ContractSpecView, OptionFetchSpec, Requirements
from strategizer.types import PositionView


class MockPortfolioView:
    """Mock implementing PortfolioView."""

    def __init__(self, cash: float = 0.0) -> None:
        self._cash = cash
        self._positions: dict[str, PositionView] = {}

    def get_positions(self) -> dict[str, PositionView]:
        return dict(self._positions)

    def get_cash(self) -> float:
        return self._cash

    def get_equity(self) -> float:
        return self._cash


class MockContractSpecView:
    """Mock implementing ContractSpecView with typed start_time/end_time."""

    def __init__(
        self,
        tick_size: float = 0.25,
        point_value: float = 50.0,
        timezone: str = "America/New_York",
        start_time: time | None = None,
        end_time: time | None = None,
    ) -> None:
        self._tick_size = tick_size
        self._point_value = point_value
        self._timezone = timezone
        self._start_time = start_time or time(9, 30)
        self._end_time = end_time or time(16, 0)

    @property
    def tick_size(self) -> float:
        return self._tick_size

    @property
    def point_value(self) -> float:
        return self._point_value

    @property
    def timezone(self) -> str:
        return self._timezone

    @property
    def start_time(self) -> time:
        return self._start_time

    @property
    def end_time(self) -> time:
        return self._end_time


def test_portfolio_view_mock() -> None:
    mock = MockPortfolioView(cash=100_000.0)
    assert mock.get_positions() == {}
    assert mock.get_cash() == 100_000.0
    assert mock.get_equity() == 100_000.0


def test_portfolio_view_with_positions() -> None:
    mock = MockPortfolioView(cash=50_000.0)
    mock._positions["ESH26"] = PositionView("ESH26", 1, 5400.0)
    assert len(mock.get_positions()) == 1
    assert mock.get_positions()["ESH26"].qty == 1


def test_contract_spec_view_mock() -> None:
    mock = MockContractSpecView()
    assert mock.tick_size == 0.25
    assert mock.point_value == 50.0
    assert mock.timezone == "America/New_York"
    assert mock.start_time == time(9, 30)
    assert mock.end_time == time(16, 0)


def test_contract_spec_view_custom_times() -> None:
    mock = MockContractSpecView(start_time=time(8, 0), end_time=time(15, 0))
    assert mock.start_time == time(8, 0)
    assert mock.end_time == time(15, 0)


def test_mock_contract_spec_view_fulfills_protocol() -> None:
    """MockContractSpecView is accepted where ContractSpecView is expected."""
    mock: ContractSpecView = MockContractSpecView()
    assert mock.tick_size == 0.25
    assert mock.start_time == time(9, 30)
    assert mock.end_time == time(16, 0)


def test_requirements_creation() -> None:
    req = Requirements(
        symbols=["ESH26", "NQH26"],
        timeframes=["1m"],
        lookback=80,
        needs_quotes=False,
    )
    assert req.symbols == ["ESH26", "NQH26"]
    assert req.timeframes == ["1m"]
    assert req.lookback == 80
    assert req.needs_quotes is False


def test_requirements_default_needs_quotes() -> None:
    req = Requirements(symbols=["ESH26"], timeframes=["1m"], lookback=80)
    assert req.needs_quotes is False


def test_requirements_immutable() -> None:
    req = Requirements(symbols=["ESH26"], timeframes=["1m"], lookback=80)
    with pytest.raises(FrozenInstanceError):
        req.lookback = 100


def test_option_fetch_spec_contract_ids() -> None:
    spec = OptionFetchSpec(contract_ids=["SPY|2026-01-17|C|480|100"])
    assert spec.contract_ids == ["SPY|2026-01-17|C|480|100"]
    assert spec.sigma_limit is None


def test_option_fetch_spec_sigma_limit() -> None:
    spec = OptionFetchSpec(sigma_limit=2.0)
    assert spec.contract_ids is None
    assert spec.sigma_limit == 2.0


def test_option_fetch_spec_empty_contract_ids() -> None:
    spec = OptionFetchSpec(contract_ids=[])
    assert spec.contract_ids == []
