"""Strategy ABC — base interface for all strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

from .protocol import OptionFetchSpec, Requirements
from .types import Signal

if TYPE_CHECKING:
    from .protocol import ContractSpecView, PortfolioView
    from .types import BarInput


class Strategy(ABC):
    """Base class for strategies. Consumes market data + portfolio, emits Signal[]."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def requirements(self) -> Requirements: ...

    @abstractmethod
    def evaluate(
        self,
        ts: datetime,
        bars_by_symbol: dict[str, dict[str, list["BarInput"]]],
        specs: dict[str, "ContractSpecView"],
        portfolio: "PortfolioView",
        *,
        step_index: int | None = None,
        strategy_params: dict | None = None,
        option_chain: list[str] | None = None,
    ) -> list[Signal]: ...

    def option_fetch_spec(
        self,
        ts: datetime,
        portfolio: "PortfolioView",
        underlying_close: float | None,
        step_index: int,
        strategy_params: dict,
    ) -> OptionFetchSpec | None:
        """Return what options to fetch. None = use config default (current behavior)."""
        return None
