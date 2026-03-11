"""Context and MarketSnapshot — read-only views of market state.

Context is the frozen snapshot passed to strategy.evaluate(). MarketSnapshot
is the serializable version for the REST API. Both are constructed by
MarketState with shallow-copied containers for snapshot isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from core.instrument import ContractSpec
from core.market_data import Bar, Quote
from core.portfolio import PortfolioState, create_mock_portfolio


@dataclass(frozen=True)
class Context:
    """Read-only view of market state passed to strategy.evaluate().

    Reasoning: Strategies must not mutate market state. Frozen dataclass
    prevents field reassignment. Container contents are shallow-copied
    by MarketState.get_context() so mutations don't leak back.
    """

    timestamp: datetime
    quotes: dict[str, Quote]
    bars: dict[str, dict[str, list[Bar]]]
    specs: dict[str, ContractSpec] = field(default_factory=dict)
    portfolio: PortfolioState = field(default_factory=create_mock_portfolio)


@dataclass
class MarketSnapshot:
    """Full state snapshot for REST API and persistence.

    Reasoning: Separate from Context (not frozen) so the API layer can
    augment it with additional fields if needed. Same copy semantics
    as Context — containers are shallow-copied by MarketState.
    """

    timestamp: datetime
    quotes: dict[str, Quote]
    bars: dict[str, dict[str, list[Bar]]]
    specs: dict[str, ContractSpec] = field(default_factory=dict)
