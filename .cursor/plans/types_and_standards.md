# Types and Standards

Conventions for strategizer service, backtester, and observer. Ensures consistent serialization and prevents client/server drift.

---

## Time

- **Internal**: All data, API payloads, serialization use **UTC** (ISO 8601: `2026-01-02T14:35:00Z`).
- **Display**: UI converts to **Central (America/Chicago)** for display only.
- **Example**: Bar at `14:35Z` displays as 9:35 AM CT.

---

## Types

| Type | Convention |
|------|------------|
| **Prices** | float; decimals as needed per instrument |
| **Quantities** | int |
| **IDs** | stable strings (UUID for orders/candidates) |

---

## SpecView (JSON)

```json
{
  "tick_size": 0.25,
  "point_value": 50,
  "session": {
    "timezone": "America/Chicago",
    "start_time": "09:30:00",
    "end_time": "16:00:00"
  }
}
```

- `start_time`, `end_time`: `"HH:MM:SS"` strings (JSON cannot serialize Python `time`).

---

## API Contract

### EvaluateContext (request)

```json
{
  "ts": "2026-01-02T14:35:00Z",
  "step_index": 1,
  "strategy_name": "orb_5m",
  "strategy_params": { "min_range_ticks": 4, "max_range_ticks": 40, "qty": 1 },
  "bars_by_symbol": { "ESH26": { "5m": [{"ts": "...", "open": 5400, "high": 5401, "low": 5399, "close": 5400.5, "volume": 100}] } },
  "specs": { "ESH26": { "tick_size": 0.25, "point_value": 50, "session": { "timezone": "America/Chicago", "start_time": "09:30:00", "end_time": "16:00:00" } } },
  "portfolio": {}
}
```

### BarInput (in bars_by_symbol)

```json
{ "ts": "2026-01-02T14:35:00Z", "open": 5400, "high": 5401, "low": 5399, "close": 5400.5, "volume": 100 }
```

- `ts`: ISO 8601 UTC string.
- For step-only strategies (buy_and_hold, covered_call), client may send minimal or empty bars; strategy uses `step_index` only.

### Signal (response item)

```json
{
  "symbol": "ESH26",
  "instrument_id": null,
  "direction": "LONG",
  "entry_type": "STOP",
  "entry_price": 5410.25,
  "stop_price": 5404.75,
  "targets": [5415.75, 5421.25],
  "qty": 1,
  "score": 80.0,
  "explain": ["ORB 5m: price broke above opening range"],
  "valid_until": "2026-01-02T16:00:00Z"
}
```

| Field | Type | Allowed values / notes |
|-------|------|------------------------|
| `direction` | str | "LONG" \| "SHORT" |
| `entry_type` | str | "MARKET" \| "LIMIT" \| "STOP" |
| `instrument_id` | str \| null | contract_id for options; null for futures/equity (use symbol) |
| `qty` | int | default 1; from strategy_params |
