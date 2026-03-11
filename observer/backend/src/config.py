"""Application configuration — load config.yaml into typed AppConfig."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from engine.config import EngineConfig

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = "config.yaml"


@dataclass
class StrategyEntry:
    """Config for a single strategy."""

    enabled: bool = True
    watchlist: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    source: str | None = None  # "strategizer" to load from strategizer package


@dataclass
class AppConfig:
    """Parsed application configuration."""

    engine: EngineConfig = field(default_factory=EngineConfig)
    watchlists: dict[str, list[str]] = field(default_factory=lambda: {"futures_main": ["ESH26"]})
    strategies: dict[str, StrategyEntry] = field(default_factory=dict)


def _default_config() -> AppConfig:
    return AppConfig(
        strategies={"dummy": StrategyEntry(enabled=True)},
    )


def load_config(path: str | None = None) -> AppConfig:
    """Load config from YAML file.

    Resolution order for file path:
    1. Explicit ``path`` argument
    2. ``OBSERVER_CONFIG`` environment variable
    3. ``config.yaml`` in current working directory

    Returns sensible defaults when the file does not exist.
    Raises ``ValueError`` on unparseable YAML.
    """
    resolved = path or os.environ.get("OBSERVER_CONFIG", _DEFAULT_CONFIG_PATH)

    config_path = Path(resolved)
    if not config_path.is_file():
        logger.info("Config file %s not found — using defaults", resolved)
        return _default_config()

    text = config_path.read_text()
    if not text.strip():
        logger.info("Config file %s is empty — using defaults", resolved)
        return _default_config()

    try:
        raw: dict[str, Any] = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid config YAML in {resolved}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Invalid config YAML in {resolved}: expected mapping at top level")

    engine_raw = raw.get("engine", {}) or {}
    engine = EngineConfig(
        eval_timeframe=engine_raw.get("eval_timeframe", "5m"),
        max_candidates_per_strategy=engine_raw.get("max_candidates_per_strategy", 10),
    )

    watchlists: dict[str, list[str]] = raw.get("watchlists") or {"futures_main": ["ESH26"]}

    strategies: dict[str, StrategyEntry] = {}
    for name, entry_raw in (raw.get("strategies") or {}).items():
        if entry_raw is None:
            entry_raw = {}
        strategies[name] = StrategyEntry(
            enabled=entry_raw.get("enabled", True),
            watchlist=entry_raw.get("watchlist"),
            params=entry_raw.get("params") or {},
            source=entry_raw.get("source"),
        )

    return AppConfig(engine=engine, watchlists=watchlists, strategies=strategies)
