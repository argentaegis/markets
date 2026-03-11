"""Mock Strategizer HTTP for golden and integration tests.

Returns deterministic signals matching strategizer service behavior
for buy_and_hold, covered_call, buy_and_hold_underlying.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch


def _mock_strategizer_responses(body: dict) -> list[dict]:
    """Return signal list for given EvaluateContext body."""
    strategy_name = body.get("strategy_name", "")
    step_index = body.get("step_index", 1)
    params = body.get("strategy_params") or {}

    if strategy_name == "buy_and_hold":
        if step_index != 1:
            return []
        contract_id = params.get("contract_id", "")
        if not contract_id:
            return []
        return [
            {
                "symbol": "",
                "instrument_id": contract_id,
                "direction": "LONG",
                "entry_type": "MARKET",
                "entry_price": 0.0,
                "stop_price": 0.0,
                "targets": [],
                "qty": int(params.get("qty", 1)),
                "score": 0.0,
                "explain": [],
                "valid_until": None,
            }
        ]

    if strategy_name == "covered_call":
        contract_id = params.get("contract_id", "")
        if not contract_id:
            return []
        exit_step = int(params.get("exit_step", 3))
        qty = int(params.get("qty", 1))
        if step_index == 1:
            return [
                {
                    "symbol": "",
                    "instrument_id": contract_id,
                    "direction": "LONG",
                    "entry_type": "MARKET",
                    "entry_price": 0.0,
                    "stop_price": 0.0,
                    "targets": [],
                    "qty": qty,
                    "score": 0.0,
                    "explain": [],
                    "valid_until": None,
                }
            ]
        if step_index == exit_step:
            return [
                {
                    "symbol": "",
                    "instrument_id": contract_id,
                    "direction": "SHORT",
                    "entry_type": "MARKET",
                    "entry_price": 0.0,
                    "stop_price": 0.0,
                    "targets": [],
                    "qty": qty,
                    "score": 0.0,
                    "explain": [],
                    "valid_until": None,
                }
            ]
        return []

    if strategy_name == "orb_5m":
        bars_by_symbol = body.get("bars_by_symbol") or {}
        for sym, tf_map in bars_by_symbol.items():
            bars = tf_map.get("1m") or []
            if bars:
                bars = bars[-6:]
                if len(bars) >= 6:
                    or_high = max(b.get("high", 0) for b in bars[:5])
                    or_low = min(b.get("low", 99999) for b in bars[:5])
                    or_low = or_low if or_low < 99999 else 5400
                    breakout = bars[-1].get("close", 0) > or_high
                else:
                    continue
            else:
                continue
            if breakout:
                tick = 0.25
                entry = round((or_high + tick) / tick) * tick
                stop = round((or_low - tick) / tick) * tick
                risk = entry - stop
                t1 = round((entry + risk) / tick) * tick
                t2 = round((entry + 2 * risk) / tick) * tick
                return [
                    {
                        "symbol": sym,
                        "instrument_id": None,
                        "direction": "LONG",
                        "entry_type": "STOP",
                        "entry_price": entry,
                        "stop_price": stop,
                        "targets": [t1, t2],
                        "qty": int(params.get("qty", 1)),
                        "score": 80.0,
                        "explain": ["ORB breakout"],
                        "valid_until": None,
                    }
                ]
        return []

    if strategy_name == "buy_and_hold_underlying":
        if step_index != 1:
            return []
        symbol = params.get("symbol", "")
        if not symbol:
            return []
        return [
            {
                "symbol": symbol,
                "instrument_id": None,
                "direction": "LONG",
                "entry_type": "MARKET",
                "entry_price": 0.0,
                "stop_price": 0.0,
                "targets": [],
                "qty": int(params.get("qty", 100)),
                "score": 0.0,
                "explain": [],
                "valid_until": None,
            }
        ]

    if strategy_name == "trend_entry_trailing_stop":
        # Return on step 1 (first bar, 14:35 ET); step 2 (15:00) bar 2 triggers trailing stop
        if step_index != 1:
            return []
        bars_by_symbol = body.get("bars_by_symbol", {})
        symbol = next(iter(bars_by_symbol.keys()), "ESH1")
        trailing_stop_ticks = int(params.get("trailing_stop_ticks", 4))
        qty = int(params.get("qty", 1))
        direction = str(params.get("direction", "LONG")).upper()
        return [
            {
                "symbol": symbol,
                "instrument_id": None,
                "direction": direction,
                "entry_type": "MARKET",
                "entry_price": 0.0,
                "stop_price": 0.0,
                "targets": [],
                "qty": qty,
                "score": 50.0,
                "explain": ["First cross MA (mock)"],
                "valid_until": None,
                "trailing_stop_ticks": trailing_stop_ticks,
            }
        ]

    return []


@contextmanager
def mock_strategizer_http():
    """Context manager that mocks requests.Session.post for Strategizer POST /evaluate."""

    def fake_post(url, data=None, **kwargs):
        body = json.loads(data) if isinstance(data, str) else json.loads(data.decode("utf-8")) if data else {}
        signals = _mock_strategizer_responses(body)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = signals
        resp.raise_for_status = MagicMock()
        return resp

    with patch("requests.Session.post", side_effect=fake_post):
        yield
