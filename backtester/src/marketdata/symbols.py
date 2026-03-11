"""Symbol mapping: user symbol -> provider-specific ticker.

User-facing symbols (e.g. SPX) may differ from provider tickers (e.g. $SPX).
YAML config enables multi-provider mapping without code changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .config import SYMBOLS_CONFIG


def load_mappings(config_path: Path | None = None) -> dict[str, dict[str, str]]:
    """Load symbol mappings from YAML. Returns {provider: {user_symbol: provider_symbol}}.

    Reasoning: Centralizes mapping; returns {} if file missing (fallback to user_symbol).
    """
    path = config_path or SYMBOLS_CONFIG
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def resolve(user_symbol: str, provider: str, config_path: Path | None = None) -> str:
    """Resolve user symbol to provider-specific ticker. Falls back to user_symbol if not mapped.

    Reasoning: Unmapped symbols pass through (e.g. SPY often same); mapped (SPX→$SPX) applied.
    """
    mappings = load_mappings(config_path)
    provider_map = mappings.get(provider, {})
    return provider_map.get(user_symbol.upper(), user_symbol)
