"""Strategies module — strategy interface and implementations."""

from __future__ import annotations

from strategies.base import BaseStrategy, Requirements
from strategies.dummy_strategy import DummyStrategy
from strategies.orb_5m import ORB5mStrategy
from strategies.registry import StrategyRegistry

__all__ = [
    "BaseStrategy",
    "DummyStrategy",
    "ORB5mStrategy",
    "Requirements",
    "StrategyRegistry",
]
