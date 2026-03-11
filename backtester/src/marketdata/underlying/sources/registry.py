"""Registry for underlying data sources."""

from __future__ import annotations

from .base import FormatConverter, MarketDataProvider
from .databento_underlying import DatabentoConverter
from .massive_underlying import MassiveConverter, MassiveProvider

_PROVIDERS: dict[str, type] = {"massive": MassiveProvider}
_CONVERTERS: dict[str, type] = {"massive": MassiveConverter, "databento": DatabentoConverter}


def get_provider(name: str, **kwargs) -> MarketDataProvider:
    """Return a provider instance for the given source name."""
    return _PROVIDERS[name](**kwargs)


def get_converter(name: str) -> FormatConverter:
    """Return a converter instance for the given source name."""
    return _CONVERTERS[name]()
