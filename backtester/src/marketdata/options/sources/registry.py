"""Registry for options data sources."""

from __future__ import annotations

from .base import (
    OptionsChainConverter,
    OptionsChainProvider,
    OptionsQuotesConverter,
    OptionsQuotesProvider,
)
from .massive_options import (
    MassiveOptionsChainConverter,
    MassiveOptionsChainProvider,
    MassiveOptionsQuotesConverter,
    MassiveOptionsQuotesProvider,
)

_CHAIN_PROVIDERS: dict[str, type] = {"massive": MassiveOptionsChainProvider}
_QUOTES_PROVIDERS: dict[str, type] = {"massive": MassiveOptionsQuotesProvider}
_CHAIN_CONVERTERS: dict[str, type] = {"massive": MassiveOptionsChainConverter}
_QUOTES_CONVERTERS: dict[str, type] = {"massive": MassiveOptionsQuotesConverter}


def get_chain_provider(name: str, **kwargs) -> OptionsChainProvider:
    """Return a chain provider instance for the given source name."""
    return _CHAIN_PROVIDERS[name](**kwargs)


def get_quotes_provider(name: str, **kwargs) -> OptionsQuotesProvider:
    """Return a quotes provider instance for the given source name."""
    return _QUOTES_PROVIDERS[name](**kwargs)


def get_chain_converter(name: str) -> OptionsChainConverter:
    """Return a chain converter instance for the given source name."""
    return _CHAIN_CONVERTERS[name]()


def get_quotes_converter(name: str) -> OptionsQuotesConverter:
    """Return a quotes converter instance for the given source name."""
    return _QUOTES_CONVERTERS[name]()
