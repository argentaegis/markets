"""BaseProvider ABC and ProviderHealth — provider protocol contract.

All market data providers implement BaseProvider. The protocol ensures canonical
types (Quote, Bar) are the only output, exceptions are wrapped, and health is
reported. get_contract_specs() lets consumers discover instrument metadata.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime

from core.instrument import ContractSpec
from core.market_data import Bar, Quote


@dataclass(frozen=True)
class ProviderHealth:
    """Snapshot of provider connection state.

    Reasoning: Engine and API need to display provider status and gate
    evaluation on connectivity. Frozen for safe sharing.
    """

    connected: bool
    source: str
    last_heartbeat: datetime | None
    message: str


class BaseProvider(ABC):
    """Abstract protocol for all market data providers.

    Reasoning: All providers must emit canonical types only. No vendor objects
    leak past this layer. Providers wrap exceptions and report health.
    get_contract_specs() provides instrument metadata (tick_size, point_value,
    session) that strategies need for price normalization and risk calculations.
    """

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def subscribe_quotes(self, symbols: list[str]) -> AsyncIterator[Quote]: ...

    @abstractmethod
    async def subscribe_bars(
        self, symbols: list[str], timeframe: str
    ) -> AsyncIterator[Bar]: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def health(self) -> ProviderHealth: ...

    @abstractmethod
    def get_contract_specs(self) -> dict[str, ContractSpec]: ...
