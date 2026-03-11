"""Tests for config.py — YAML config parsing into typed AppConfig."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import pytest
import yaml

from config import AppConfig, StrategyEntry, load_config
from engine.config import EngineConfig


VALID_YAML = textwrap.dedent("""\
    watchlists:
      futures_main:
        - ESH26
        - NQH26

    strategies:
      orb_5m:
        enabled: true
        watchlist: futures_main
        params:
          min_range_ticks: 4
          max_range_ticks: 40
      dummy:
        enabled: false

    engine:
      eval_timeframe: "5m"
      max_candidates_per_strategy: 10
""")


class TestLoadConfigValidFile:
    def test_returns_app_config(self, tmp_path: Path):
        p = tmp_path / "config.yaml"
        p.write_text(VALID_YAML)
        cfg = load_config(str(p))
        assert isinstance(cfg, AppConfig)

    def test_engine_section(self, tmp_path: Path):
        p = tmp_path / "config.yaml"
        p.write_text(VALID_YAML)
        cfg = load_config(str(p))
        assert cfg.engine == EngineConfig(eval_timeframe="5m", max_candidates_per_strategy=10)

    def test_watchlists_parsed(self, tmp_path: Path):
        p = tmp_path / "config.yaml"
        p.write_text(VALID_YAML)
        cfg = load_config(str(p))
        assert cfg.watchlists == {"futures_main": ["ESH26", "NQH26"]}

    def test_strategy_entries(self, tmp_path: Path):
        p = tmp_path / "config.yaml"
        p.write_text(VALID_YAML)
        cfg = load_config(str(p))
        assert "orb_5m" in cfg.strategies
        assert "dummy" in cfg.strategies
        orb = cfg.strategies["orb_5m"]
        assert orb.enabled is True
        assert orb.watchlist == "futures_main"
        assert orb.params == {"min_range_ticks": 4, "max_range_ticks": 40}
        assert cfg.strategies["dummy"].enabled is False

    def test_strategy_entry_source_parsed(self, tmp_path: Path):
        p = tmp_path / "config.yaml"
        p.write_text(textwrap.dedent("""\
            strategies:
              orb_5m:
                enabled: true
                source: strategizer
                params:
                  min_range_ticks: 4
        """))
        cfg = load_config(str(p))
        assert cfg.strategies["orb_5m"].source == "strategizer"

    def test_strategy_entry_defaults(self, tmp_path: Path):
        p = tmp_path / "config.yaml"
        p.write_text(textwrap.dedent("""\
            strategies:
              orb_5m:
                enabled: true
        """))
        cfg = load_config(str(p))
        entry = cfg.strategies["orb_5m"]
        assert entry.watchlist is None
        assert entry.params == {}
        assert entry.source is None


class TestLoadConfigMissingFile:
    def test_missing_file_returns_defaults(self, tmp_path: Path):
        cfg = load_config(str(tmp_path / "nonexistent.yaml"))
        assert isinstance(cfg, AppConfig)

    def test_default_engine(self, tmp_path: Path):
        cfg = load_config(str(tmp_path / "nonexistent.yaml"))
        assert cfg.engine == EngineConfig()

    def test_default_watchlists(self, tmp_path: Path):
        cfg = load_config(str(tmp_path / "nonexistent.yaml"))
        assert cfg.watchlists == {"futures_main": ["ESH26"]}

    def test_default_strategies(self, tmp_path: Path):
        cfg = load_config(str(tmp_path / "nonexistent.yaml"))
        assert "dummy" in cfg.strategies
        assert cfg.strategies["dummy"].enabled is True


class TestLoadConfigInvalidYAML:
    def test_invalid_yaml_raises(self, tmp_path: Path):
        p = tmp_path / "config.yaml"
        p.write_text("{{bad yaml: [")
        with pytest.raises(ValueError, match="(?i)invalid.*config"):
            load_config(str(p))


class TestLoadConfigMissingSections:
    def test_missing_engine_uses_defaults(self, tmp_path: Path):
        p = tmp_path / "config.yaml"
        p.write_text(textwrap.dedent("""\
            strategies:
              dummy:
                enabled: true
        """))
        cfg = load_config(str(p))
        assert cfg.engine == EngineConfig()

    def test_missing_watchlists_uses_defaults(self, tmp_path: Path):
        p = tmp_path / "config.yaml"
        p.write_text(textwrap.dedent("""\
            strategies:
              dummy:
                enabled: true
        """))
        cfg = load_config(str(p))
        assert cfg.watchlists == {"futures_main": ["ESH26"]}

    def test_missing_strategies_returns_empty(self, tmp_path: Path):
        p = tmp_path / "config.yaml"
        p.write_text(textwrap.dedent("""\
            engine:
              eval_timeframe: "5m"
        """))
        cfg = load_config(str(p))
        assert cfg.strategies == {}

    def test_empty_file_returns_defaults(self, tmp_path: Path):
        p = tmp_path / "config.yaml"
        p.write_text("")
        cfg = load_config(str(p))
        assert isinstance(cfg, AppConfig)
        assert cfg.engine == EngineConfig()


class TestStrategyEntry:
    def test_defaults(self):
        entry = StrategyEntry()
        assert entry.enabled is True
        assert entry.watchlist is None
        assert entry.params == {}
        assert entry.source is None


class TestLoadConfigEnvVar:
    def test_env_var_overrides_default_path(self, tmp_path: Path, monkeypatch):
        p = tmp_path / "custom.yaml"
        p.write_text(VALID_YAML)
        monkeypatch.setenv("OBSERVER_CONFIG", str(p))
        cfg = load_config()
        assert cfg.watchlists == {"futures_main": ["ESH26", "NQH26"]}
