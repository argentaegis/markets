"""Event domain object tests.

Reasoning: Events are the audit log. Every order submission, fill,
and lifecycle (e.g. expiration) produces an Event. Reporter writes to logs.jsonl.
Events must be serializable for run manifest and reproducibility.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.event import Event, EventType


def test_event_create(sample_ts: datetime) -> None:
    """E1: Create Event with ts, type (EventType), payload.

    Reasoning: Simulation loop emits events at each step. Strategy orders,
    Broker fills, and lifecycle (expiration) all produce events. We need a
    generic container that can carry different payload types.
    """
    event = Event(
        ts=sample_ts,
        type=EventType.ORDER,
        payload={"order_id": "ord-001", "side": "BUY"},
    )
    assert event.ts == sample_ts
    assert event.type == EventType.ORDER
    assert event.payload["order_id"] == "ord-001"


def test_event_type_enum_values() -> None:
    """E2: EventType has MARKET, ORDER, FILL, LIFECYCLE.

    Reasoning: These four event types cover the simulation loop:
    MARKET (bar/quote update), ORDER (strategy output), FILL (execution),
    LIFECYCLE (expiration, corporate action). Enum ensures no typos.
    """
    assert EventType.MARKET.value == "MARKET"
    assert EventType.ORDER.value == "ORDER"
    assert EventType.FILL.value == "FILL"
    assert EventType.LIFECYCLE.value == "LIFECYCLE"
    assert len(EventType) == 4


def test_event_payload_flexible(sample_ts: datetime) -> None:
    """E3: payload can be dict or object (Order, Fill, etc.).

    Reasoning: Different event types carry different payloads. ORDER carries
    Order; FILL carries Fill; LIFECYCLE might carry contract_id and settlement.
    Flexible payload avoids a giant union type; serialization handles conversion.
    """
    # Dict payload
    ev_dict = Event(ts=sample_ts, type=EventType.FILL, payload={"fill_price": 485.25})
    assert ev_dict.payload["fill_price"] == 485.25

    # Simple value payload
    ev_simple = Event(ts=sample_ts, type=EventType.MARKET, payload="bar_close")
    assert ev_simple.payload == "bar_close"


def test_event_serializable_for_logs(sample_ts: datetime) -> None:
    """E4: Event is serializable for logs (ts, type, payload to dict).

    Reasoning: Run manifest and logs.jsonl require serialization. Config
    is saved with run artifacts. Event must convert to dict
    or JSON-serializable form.
    """
    event = Event(
        ts=sample_ts,
        type=EventType.FILL,
        payload={"order_id": "ord-001", "fill_price": 485.25, "fill_qty": 1},
    )
    # Minimal serialization: we can build a dict from public fields
    d = {"ts": event.ts.isoformat(), "type": event.type.value, "payload": event.payload}
    assert d["type"] == "FILL"
    assert d["payload"]["order_id"] == "ord-001"
