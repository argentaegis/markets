"""Tests for Position, PortfolioState, create_mock_portfolio."""

from __future__ import annotations

import pytest

from core.portfolio import Position, PortfolioState, create_mock_portfolio


class TestPosition:
    def test_creation(self):
        pos = Position(instrument_id="ESH26", qty=2, avg_price=5400.50)
        assert pos.instrument_id == "ESH26"
        assert pos.qty == 2
        assert pos.avg_price == 5400.50

    def test_short_position(self):
        pos = Position(instrument_id="NQH26", qty=-1, avg_price=19500.0)
        assert pos.qty == -1


class TestPortfolioState:
    def test_empty(self):
        portfolio = PortfolioState(cash=0.0, positions={})
        assert portfolio.cash == 0.0
        assert portfolio.positions == {}

    def test_with_positions(self):
        pos = Position(instrument_id="ESH26", qty=1, avg_price=5400.0)
        portfolio = PortfolioState(cash=100_000.0, positions={"ESH26": pos})
        assert portfolio.cash == 100_000.0
        assert len(portfolio.positions) == 1
        assert portfolio.positions["ESH26"].qty == 1


class TestCreateMockPortfolio:
    def test_returns_empty_portfolio(self):
        portfolio = create_mock_portfolio()
        assert portfolio.cash == 0.0
        assert portfolio.positions == {}

    def test_each_call_returns_new_instance(self):
        a = create_mock_portfolio()
        b = create_mock_portfolio()
        assert a is not b
