"""Paths and defaults for marketdata CLI.

Pre-backtest phase: fetch from providers ( Massive, etc. ), cache in Parquet,
export to Parquet or CSV for DataProvider. CACHE_ROOT matches loader expectation;
SYMBOLS_CONFIG enables provider-specific ticker mapping.
"""

from __future__ import annotations

from pathlib import Path

# Package root: src/marketdata
_PACKAGE_ROOT = Path(__file__).resolve().parent
# Project root: parent of src
_PROJECT_ROOT = _PACKAGE_ROOT.parent.parent

# Project root and cache directory
# Underlying: cache/{provider}/underlying/{interval}/{symbol}/bars_*.parquet
# Options: cache/{provider}/options/{symbol}/metadata/, quotes/
PROJECT_ROOT = _PROJECT_ROOT
CACHE_ROOT = _PROJECT_ROOT / "data" / "cache"

# Symbol mapping: bundled default inside package
SYMBOLS_CONFIG = _PACKAGE_ROOT / "symbols.yaml"
