"""Dataclass → dict helpers for JSON serialization.

Plain functions that convert frozen dataclasses into JSON-safe dicts.
datetime → ISO 8601 string, Enum → .value string, everything else passes through.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from core.candidate import TradeCandidate
from core.market_data import Bar, Quote
from state.context import MarketSnapshot


def _convert_value(val: Any) -> Any:
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, Enum):
        return val.value
    return val


def serialize_quote(quote: Quote) -> dict[str, Any]:
    return {
        "symbol": quote.symbol,
        "bid": quote.bid,
        "ask": quote.ask,
        "last": quote.last,
        "bid_size": quote.bid_size,
        "ask_size": quote.ask_size,
        "volume": quote.volume,
        "timestamp": _convert_value(quote.timestamp),
        "source": quote.source,
        "quality": _convert_value(quote.quality),
    }


def serialize_bar(bar: Bar) -> dict[str, Any]:
    return {
        "symbol": bar.symbol,
        "timeframe": bar.timeframe,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "timestamp": _convert_value(bar.timestamp),
        "source": bar.source,
        "quality": _convert_value(bar.quality),
    }


def serialize_candidate(candidate: TradeCandidate) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "symbol": candidate.symbol,
        "strategy": candidate.strategy,
        "direction": _convert_value(candidate.direction),
        "entry_type": _convert_value(candidate.entry_type),
        "entry_price": candidate.entry_price,
        "stop_price": candidate.stop_price,
        "targets": list(candidate.targets),
        "score": candidate.score,
        "explain": list(candidate.explain),
        "valid_until": _convert_value(candidate.valid_until),
        "tags": dict(candidate.tags),
        "created_at": _convert_value(candidate.created_at),
    }


def serialize_snapshot(
    snapshot: MarketSnapshot,
    candidates: list[TradeCandidate],
) -> dict[str, Any]:
    return {
        "quotes": {
            sym: serialize_quote(q)
            for sym, q in snapshot.quotes.items()
        },
        "bars": {
            sym: {
                tf: [serialize_bar(b) for b in bar_list]
                for tf, bar_list in tf_map.items()
            }
            for sym, tf_map in snapshot.bars.items()
        },
        "candidates": [serialize_candidate(c) for c in candidates],
    }
