"""Protocols — PortfolioView, ContractSpecView, Requirements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Protocol

from .types import PositionView


class PortfolioView(Protocol):
    """Read-only view of portfolio for strategy decisions."""

    def get_positions(self) -> dict[str, PositionView]: ...
    def get_cash(self) -> float: ...
    def get_equity(self) -> float: ...


class ContractSpecView(Protocol):
    """Minimal contract spec for tick_size, point_value, session."""

    @property
    def tick_size(self) -> float: ...

    @property
    def point_value(self) -> float: ...

    @property
    def timezone(self) -> str: ...

    @property
    def start_time(self) -> time: ...

    @property
    def end_time(self) -> time: ...


@dataclass(frozen=True)
class Requirements:
    """Data requirements declared by a strategy."""

    symbols: list[str]
    timeframes: list[str]
    lookback: int
    needs_quotes: bool = False


@dataclass(frozen=True)
class OptionFetchSpec:
    """What option data to fetch. None = use config default (full or sigma-filtered)."""

    contract_ids: list[str] | None = None  # Explicit IDs; [] = only positions (marks)
    sigma_limit: float | None = None  # When contract_ids is None: filtered chain
