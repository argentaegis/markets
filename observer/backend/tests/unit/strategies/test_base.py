"""Tests for BaseStrategy ABC and Requirements dataclass."""

from __future__ import annotations

import pytest

from strategies.base import BaseStrategy, Requirements


class TestBaseStrategyIsAbstract:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseStrategy()

    def test_has_three_abstract_members(self):
        abstracts = BaseStrategy.__abstractmethods__
        assert len(abstracts) == 3
        assert "name" in abstracts
        assert "requirements" in abstracts
        assert "evaluate" in abstracts


class TestRequirements:
    def test_creation(self):
        req = Requirements(
            symbols=["ESH26"],
            timeframes=["5m"],
            lookback=10,
            needs_quotes=True,
        )
        assert req.symbols == ["ESH26"]
        assert req.timeframes == ["5m"]
        assert req.lookback == 10
        assert req.needs_quotes is True

    def test_needs_quotes_defaults_false(self):
        req = Requirements(symbols=["ESH26"], timeframes=["5m"], lookback=1)
        assert req.needs_quotes is False

    def test_frozen(self):
        req = Requirements(symbols=["ESH26"], timeframes=["5m"], lookback=1)
        with pytest.raises(AttributeError):
            req.lookback = 20

    def test_multiple_symbols_and_timeframes(self):
        req = Requirements(
            symbols=["ESH26", "NQH26"],
            timeframes=["1m", "5m"],
            lookback=20,
        )
        assert len(req.symbols) == 2
        assert len(req.timeframes) == 2
