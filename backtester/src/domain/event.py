"""Event — audit log: ts, type (MARKET/ORDER/FILL/LIFECYCLE), payload.

Audit trail for replay, debugging, and reporting. Each simulation tick can append
MARKET/ORDER/FILL/LIFECYCLE events. Payload typed for downstream consumers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Event types for simulation loop."""

    MARKET = "MARKET"
    ORDER = "ORDER"
    FILL = "FILL"
    LIFECYCLE = "LIFECYCLE"


@dataclass
class Event:
    """Event for audit log. Payload can be dict or domain object.

    Reasoning: Single event model for all simulation phases. type filters event stream;
    payload holds snapshot/order/fill/status. Enables deterministic replay.
    """

    ts: datetime
    type: EventType
    payload: dict[str, Any] | Any
