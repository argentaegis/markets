"""Tests for EngineConfig."""

from __future__ import annotations

import pytest

from engine.config import EngineConfig


class TestEngineConfig:
    def test_default_eval_timeframe(self):
        cfg = EngineConfig()
        assert cfg.eval_timeframe == "5m"

    def test_custom_eval_timeframe(self):
        cfg = EngineConfig(eval_timeframe="1m")
        assert cfg.eval_timeframe == "1m"

    def test_default_max_candidates_per_strategy(self):
        cfg = EngineConfig()
        assert cfg.max_candidates_per_strategy == 10

    def test_custom_max_candidates_per_strategy(self):
        cfg = EngineConfig(max_candidates_per_strategy=5)
        assert cfg.max_candidates_per_strategy == 5

    def test_frozen(self):
        cfg = EngineConfig()
        with pytest.raises(AttributeError):
            cfg.eval_timeframe = "15m"
