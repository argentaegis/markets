"""EngineConfig — configuration for the evaluation engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EngineConfig:
    """Configuration for the evaluation engine.

    Reasoning: Separating config from Engine allows tests to inject
    different configs without subclassing.
    """

    eval_timeframe: str = "5m"
    max_candidates_per_strategy: int = 10
