"""Provider layer — data source abstraction and implementations.

BaseProvider defines the protocol; concrete providers (SimProvider, SchwabProvider)
implement it. All providers emit only canonical core types.
"""

from .base import BaseProvider, ProviderHealth
from .schwab_provider import SchwabProvider
from .sim_provider import SimProvider

__all__ = [
    "BaseProvider",
    "ProviderHealth",
    "SchwabProvider",
    "SimProvider",
]
