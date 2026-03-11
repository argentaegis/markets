"""Tests for StrategyRegistry — discovery and instantiation of strategies."""

from __future__ import annotations

from config import AppConfig, StrategyEntry
from engine.config import EngineConfig
from strategies.base import BaseStrategy
from strategies.dummy_strategy import DummyStrategy
from strategies.orb_5m import ORB5mStrategy
from strategies.registry import StrategyRegistry


class TestDiscovery:
    def test_returns_dict(self):
        reg = StrategyRegistry()
        discovered = reg.discover()
        assert isinstance(discovered, dict)

    def test_finds_dummy(self):
        reg = StrategyRegistry()
        discovered = reg.discover()
        assert "dummy" in discovered
        assert discovered["dummy"] is DummyStrategy

    def test_finds_orb_5m(self):
        reg = StrategyRegistry()
        discovered = reg.discover()
        assert "orb_5m" in discovered
        assert discovered["orb_5m"] is ORB5mStrategy

    def test_excludes_abstract_base(self):
        reg = StrategyRegistry()
        discovered = reg.discover()
        for cls in discovered.values():
            assert cls is not BaseStrategy

    def test_all_values_are_base_strategy_subclasses(self):
        reg = StrategyRegistry()
        discovered = reg.discover()
        for cls in discovered.values():
            assert issubclass(cls, BaseStrategy)

    def test_keys_match_class_name_constants(self):
        reg = StrategyRegistry()
        discovered = reg.discover()
        for name, cls in discovered.items():
            assert name == cls.NAME

    def test_discovery_is_repeatable(self):
        reg = StrategyRegistry()
        d1 = reg.discover()
        d2 = reg.discover()
        assert d1 == d2


def _config(
    strategies: dict[str, StrategyEntry] | None = None,
    watchlists: dict[str, list[str]] | None = None,
) -> AppConfig:
    return AppConfig(
        engine=EngineConfig(),
        watchlists=watchlists or {"futures_main": ["ESH26", "NQH26"]},
        strategies=strategies or {},
    )


class TestInstantiation:
    def test_creates_enabled_strategy(self):
        reg = StrategyRegistry()
        cfg = _config(strategies={"dummy": StrategyEntry(enabled=True)})
        instances = reg.instantiate(cfg)
        assert len(instances) == 1
        assert isinstance(instances[0], DummyStrategy)

    def test_skips_disabled_strategy(self):
        reg = StrategyRegistry()
        cfg = _config(strategies={"dummy": StrategyEntry(enabled=False)})
        instances = reg.instantiate(cfg)
        assert len(instances) == 0

    def test_resolves_watchlist_to_symbols(self):
        reg = StrategyRegistry()
        cfg = _config(
            strategies={"dummy": StrategyEntry(enabled=True, watchlist="futures_main")},
            watchlists={"futures_main": ["NQH26"]},
        )
        instances = reg.instantiate(cfg)
        assert instances[0]._symbols == ["NQH26"]

    def test_merges_symbols_with_params(self):
        reg = StrategyRegistry()
        cfg = _config(
            strategies={
                "orb_5m": StrategyEntry(
                    enabled=True,
                    watchlist="futures_main",
                    params={"min_range_ticks": 8, "max_range_ticks": 20},
                ),
            },
            watchlists={"futures_main": ["NQH26"]},
        )
        instances = reg.instantiate(cfg)
        assert len(instances) == 1
        s = instances[0]
        assert isinstance(s, ORB5mStrategy)
        assert s._symbols == ["NQH26"]
        assert s._min_range_ticks == 8
        assert s._max_range_ticks == 20

    def test_no_watchlist_uses_strategy_default(self):
        reg = StrategyRegistry()
        cfg = _config(strategies={"dummy": StrategyEntry(enabled=True)})
        instances = reg.instantiate(cfg)
        assert instances[0]._symbols == ["ESH26"]

    def test_unknown_strategy_skipped(self):
        reg = StrategyRegistry()
        cfg = _config(strategies={"nonexistent": StrategyEntry(enabled=True)})
        instances = reg.instantiate(cfg)
        assert len(instances) == 0

    def test_bad_params_skipped(self):
        reg = StrategyRegistry()
        cfg = _config(
            strategies={
                "dummy": StrategyEntry(
                    enabled=True,
                    params={"totally_invalid_kwarg": 999},
                ),
            },
        )
        instances = reg.instantiate(cfg)
        assert len(instances) == 0

    def test_multiple_strategies(self):
        reg = StrategyRegistry()
        cfg = _config(
            strategies={
                "dummy": StrategyEntry(enabled=True),
                "orb_5m": StrategyEntry(
                    enabled=True,
                    watchlist="futures_main",
                    params={"min_range_ticks": 4, "max_range_ticks": 40},
                ),
            },
            watchlists={"futures_main": ["ESH26"]},
        )
        instances = reg.instantiate(cfg)
        assert len(instances) == 2
        names = {s.name for s in instances}
        assert names == {"dummy", "orb_5m"}

    def test_uses_provided_discovered_map(self):
        reg = StrategyRegistry()
        cfg = _config(strategies={"dummy": StrategyEntry(enabled=True)})
        discovered = {"dummy": DummyStrategy}
        instances = reg.instantiate(cfg, discovered=discovered)
        assert len(instances) == 1
