"""Strategy ABC — base interface for all strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

from .protocol import Requirements
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
    ) -> list[Signal]: ...
