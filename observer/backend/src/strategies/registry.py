"""StrategyRegistry — discovers and instantiates strategy classes.

Strategies are added by dropping a Python file in the strategies/ package
and enabling them in config.yaml. When config says source=strategizer,
loads from strategizer package and wraps in StrategizerStrategyAdapter.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import TYPE_CHECKING, Any

import strategies
from strategies.base import BaseStrategy

if TYPE_CHECKING:
    from config import AppConfig

logger = logging.getLogger(__name__)

_SKIP_MODULES = {"base", "registry", "http_strategizer", "__init__"}


class StrategyRegistry:
    """Discovers and instantiates strategy classes from the strategies/ package."""

    def discover(self) -> dict[str, type[BaseStrategy]]:
        """Scan strategies/ for concrete BaseStrategy subclasses with a NAME attribute."""
        found: dict[str, type[BaseStrategy]] = {}

        pkg_path = strategies.__path__
        for finder, module_name, _ispkg in pkgutil.iter_modules(pkg_path):
            if module_name in _SKIP_MODULES:
                continue
            fqn = f"strategies.{module_name}"
            try:
                mod = importlib.import_module(fqn)
            except Exception:
                logger.warning("Failed to import %s — skipping", fqn, exc_info=True)
                continue

            for _attr_name, obj in inspect.getmembers(mod, inspect.isclass):
                if (
                    issubclass(obj, BaseStrategy)
                    and not inspect.isabstract(obj)
                    and hasattr(obj, "NAME")
                ):
                    found[obj.NAME] = obj

        logger.info("Discovered strategies: %s", ", ".join(sorted(found)))
        return found

    def instantiate(
        self,
        config: AppConfig,
        discovered: dict[str, type[BaseStrategy]] | None = None,
    ) -> list[BaseStrategy]:
        """Create enabled strategy instances with configured params.

        For each enabled strategy in config:
        1. Look up class from discovered map (or call discover())
        2. Resolve watchlist name to symbol list
        3. Merge symbols into params dict
        4. Call constructor with **params unpacking
        """
        if discovered is None:
            discovered = self.discover()

        instances: list[BaseStrategy] = []

        for name, entry in config.strategies.items():
            if not entry.enabled:
                logger.info("Strategy %s is disabled — skipping", name)
                continue

            params: dict[str, Any] = dict(entry.params)
            if entry.watchlist:
                symbols = config.watchlists.get(entry.watchlist)
                if symbols is None:
                    logger.warning(
                        "Watchlist '%s' for strategy '%s' not found — skipping symbols",
                        entry.watchlist,
                        name,
                    )
                else:
                    params["symbols"] = list(symbols)

            if entry.source == "strategizer":
                try:
                    from strategies.http_strategizer import HttpStrategizerAdapter
                    from engine.config import EngineConfig
                    eval_timeframe = config.engine.eval_timeframe if config.engine else "5m"
                    instance = HttpStrategizerAdapter(
                        strategy_name=name,
                        strategy_params=params,
                        eval_timeframe=eval_timeframe,
                    )
                    instances.append(instance)
                    logger.info("Instantiated strategy '%s' via HTTP strategizer with params %s", name, params)
                except Exception as exc:
                    logger.warning(
                        "Failed to instantiate HTTP strategizer '%s' with params %s: %s",
                        name,
                        params,
                        exc,
                    )
                continue

            cls = discovered.get(name)
            if cls is None:
                logger.warning("Strategy '%s' in config not found in registry — skipping", name)
                continue

            try:
                instance = cls(**params)
                instances.append(instance)
                logger.info("Instantiated strategy '%s' with params %s", name, params)
            except TypeError as exc:
                logger.warning(
                    "Failed to instantiate strategy '%s' with params %s: %s",
                    name,
                    params,
                    exc,
                )

        return instances
