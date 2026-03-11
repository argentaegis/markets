"""HttpStrategizerAdapter — calls Strategizer service via HTTP.

Implements BaseStrategy; engine calls evaluate(ctx). No local strategizer import.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta

from core.candidate import Direction, EntryType, TradeCandidate
from strategies.base import BaseStrategy, Requirements
from state.context import Context

logger = logging.getLogger(__name__)

_STRATEGIZER_URL = os.environ.get("STRATEGIZER_URL", "http://localhost:8001")

_STRATEGY_REQUIREMENTS: dict[str, Requirements] = {
    "orb_5m": Requirements(symbols=["ESH26"], timeframes=["5m"], lookback=80, needs_quotes=False),
    "buy_and_hold": Requirements(symbols=[], timeframes=[], lookback=0, needs_quotes=False),
    "buy_and_hold_underlying": Requirements(symbols=[], timeframes=[], lookback=0, needs_quotes=False),
    "covered_call": Requirements(symbols=[], timeframes=[], lookback=0, needs_quotes=False),
}


def _bar_to_dict(bar) -> dict:
    ts = getattr(bar, "timestamp", None) or getattr(bar, "ts", None)
    ts_str = ts.isoformat() if ts and hasattr(ts, "isoformat") else str(ts) if ts else ""
    return {
        "ts": ts_str,
        "open": getattr(bar, "open", 0),
        "high": getattr(bar, "high", 0),
        "low": getattr(bar, "low", 0),
        "close": getattr(bar, "close", 0),
        "volume": float(getattr(bar, "volume", 0)),
    }


def _spec_to_dict(spec) -> dict:
    sess = getattr(spec, "session", None)
    if sess:
        start = getattr(sess, "start_time", "09:30:00")
        end = getattr(sess, "end_time", "16:00:00")
        start_str = start.strftime("%H:%M:%S") if hasattr(start, "strftime") else str(start)
        end_str = end.strftime("%H:%M:%S") if hasattr(end, "strftime") else str(end)
        timezone = getattr(sess, "timezone", "America/New_York")
    else:
        start_str, end_str, timezone = "09:30:00", "16:00:00", "America/New_York"
    return {
        "tick_size": float(getattr(spec, "tick_size", 0.25)),
        "point_value": float(getattr(spec, "point_value", 50.0)),
        "session": {"timezone": timezone, "start_time": start_str, "end_time": end_str},
    }


def _build_evaluate_body(
    ctx: Context,
    strategy_name: str,
    strategy_params: dict,
    step_index: int,
    eval_timeframe: str,
    primary_symbol: str | None,
) -> dict:
    ts = ctx.timestamp
    ts_str = ts.isoformat() if ts.tzinfo else str(ts)

    bars_by_symbol: dict[str, dict[str, list[dict]]] = {}
    for sym, tf_map in ctx.bars.items():
        bars_by_symbol[sym] = {}
        for tf, bars in tf_map.items():
            bars_by_symbol[sym][tf] = [_bar_to_dict(b) for b in (bars or [])]

    specs = {k: _spec_to_dict(v) for k, v in ctx.specs.items()}
    if not specs:
        specs["_"] = {"tick_size": 0.25, "point_value": 50.0, "session": {"timezone": "America/New_York", "start_time": "09:30:00", "end_time": "16:00:00"}}

    return {
        "ts": ts_str,
        "step_index": step_index,
        "strategy_name": strategy_name,
        "strategy_params": strategy_params,
        "bars_by_symbol": bars_by_symbol,
        "specs": specs,
        "portfolio": {},
    }


def _signal_to_trade_candidate(d: dict, strategy_name: str, created_at: datetime) -> TradeCandidate:
    symbol = d.get("symbol") or ""
    instrument_id = d.get("instrument_id")
    if instrument_id:
        symbol = instrument_id
    direction = Direction(d.get("direction", "LONG"))
    entry_type = EntryType(d.get("entry_type", "MARKET"))
    valid_until_raw = d.get("valid_until")
    valid_until = (
        datetime.fromisoformat(valid_until_raw.replace("Z", "+00:00"))
        if valid_until_raw
        else created_at + timedelta(hours=1)
    )
    return TradeCandidate(
        id=str(uuid.uuid4()),
        symbol=symbol,
        strategy=strategy_name,
        direction=direction,
        entry_type=entry_type,
        entry_price=float(d.get("entry_price", 0)),
        stop_price=float(d.get("stop_price", 0)),
        targets=list(d.get("targets") or []),
        score=float(d.get("score", 0)),
        explain=list(d.get("explain") or []),
        valid_until=valid_until,
        tags={"strategy": strategy_name, "source": "strategizer_http"},
        created_at=created_at,
    )


class HttpStrategizerAdapter(BaseStrategy):
    """Calls Strategizer service via HTTP. No local strategizer package."""

    def __init__(
        self,
        strategy_name: str,
        strategy_params: dict,
        strategizer_url: str | None = None,
        eval_timeframe: str = "5m",
    ) -> None:
        self._strategy_name = strategy_name
        self._strategy_params = strategy_params
        self._url = (strategizer_url or _STRATEGIZER_URL).rstrip("/")
        self._eval_timeframe = eval_timeframe

    @property
    def name(self) -> str:
        return self._strategy_name

    def requirements(self) -> Requirements:
        return _STRATEGY_REQUIREMENTS.get(
            self._strategy_name,
            Requirements(symbols=[], timeframes=[], lookback=0),
        )

    def evaluate(self, ctx: Context) -> list[TradeCandidate]:
        params = dict(self._strategy_params)
        primary_symbol = (params.get("symbols") or [None])[0] if params.get("symbols") else None
        if not primary_symbol and ctx.bars:
            primary_symbol = list(ctx.bars.keys())[0]
        step_index = len(ctx.bars.get(primary_symbol or "", {}).get(self._eval_timeframe, []))

        body = _build_evaluate_body(
            ctx,
            self._strategy_name,
            params,
            step_index,
            self._eval_timeframe,
            primary_symbol,
        )

        try:
            import urllib.error
            import urllib.request
            req = urllib.request.Request(
                f"{self._url}/evaluate",
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status >= 400:
                    logger.error("Strategizer returned %s: %s", resp.status, resp.read())
                    raise RuntimeError(f"Strategizer returned {resp.status}")
                data = json.loads(resp.read().decode())
        except urllib.error.URLError as e:
            logger.error("Strategizer unreachable: %s", e)
            raise RuntimeError(f"Strategizer unreachable: {self._url}") from e

        signals = data if isinstance(data, list) else []
        return [_signal_to_trade_candidate(s, self._strategy_name, ctx.timestamp) for s in signals]
