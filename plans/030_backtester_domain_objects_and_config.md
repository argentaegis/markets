---
name: 030 Domain Objects and Config
overview: Complete the canonical domain objects and add BacktestConfig per 000_options_backtester_mvp.md §3 and §8. Add Order, Fill, Position, PortfolioState, Event, and BacktestConfig so the backtest engine loop (steps 2–7) can be built on stable types.
todos: []
isProject: false
---

# 030: Domain Objects + Config (complete step 1 of 000 MVP)

## Objective

Per [000_options_backtester_mvp.md](planning/000_options_backtester_mvp.md) §8, step 1 is "Domain objects + config". Domain layer is partially done; add the remaining objects and typed config.

## Current State

**Done:** BarRow, Bars, Quote, Quotes, ContractSpec, contract_id (parse/format), MarketSnapshot, build_market_snapshot.

**Missing (from 000 §3):**

- Order
- Fill
- Position
- PortfolioState
- Event

**Missing (from 000 §4 A4):**

- BacktestConfig (typed run config)

## Target Domain Objects

From 000 §3 (exact field list):


| Object             | Fields                                                                                        |
| ------------------ | --------------------------------------------------------------------------------------------- |
| **Order**          | id, ts, symbol/contract_id, side, qty, order_type (market/limit), limit_price (optional), tif |
| **Fill**           | order_id, ts, fill_price, fill_qty, fees, liquidity_flag (optional)                           |
| **Position**       | instrument_id, qty, avg_price, multiplier, instrument_type                                    |
| **PortfolioState** | cash, positions (map), realized_pnl, unrealized_pnl, equity                                  |
| **Event**          | ts, type (MARKET/ORDER/FILL/LIFECYCLE), payload                                              |


All IDs stable strings. Use `dataclass` (or `frozen=True` where immutability is intended). Type hints throughout.

## BacktestConfig (typed config)

Per 000 §4 A4 and §4 A5:

- All runs driven by typed `BacktestConfig`
- Config saved with run artifacts
- Any stochastic behavior uses seeded RNG from config

Minimal fields for MVP:

- `symbol: str` — underlying symbol
- `start: datetime`, `end: datetime` — data range
- `timeframe_base: str` — e.g. `"1d"`, `"1h"`, `"1m"`
- `seed: int | None` — RNG seed for determinism (None = no stochastic)
- `data_provider_config: DataProviderConfig | Path` — already exists in loader
- Optional: `synthetic_spread_ticks`, `fee_per_contract`, etc. (can add as needed)

## Implementation

### 1. Create [domain/order.py](src/domain/order.py)

```python
@dataclass(frozen=True)
class Order:
    id: str
    ts: datetime
    instrument_id: str  # contract_id for options, symbol for underlying
    side: str  # "BUY" | "SELL"
    qty: int
    order_type: str  # "market" | "limit"
    limit_price: float | None = None
    tif: str = "GTC"  # GTC, IOC, etc.
```

### 2. Create [domain/fill.py](src/domain/fill.py)

```python
@dataclass
class Fill:
    order_id: str
    ts: datetime
    fill_price: float
    fill_qty: int
    fees: float = 0.0
    liquidity_flag: str | None = None
```

### 3. Create [domain/position.py](src/domain/position.py)

```python
@dataclass
class Position:
    instrument_id: str
    qty: int
    avg_price: float
    multiplier: float
    instrument_type: str  # "option" | "underlying"
```

### 4. Create [domain/portfolio.py](src/domain/portfolio.py)

```python
@dataclass
class PortfolioState:
    cash: float
    positions: dict[str, Position]  # instrument_id -> Position
    realized_pnl: float
    unrealized_pnl: float
    equity: float
```

### 5. Create [domain/event.py](src/domain/event.py)

```python
class EventType(str, Enum):
    MARKET = "MARKET"
    ORDER = "ORDER"
    FILL = "FILL"
    LIFECYCLE = "LIFECYCLE"

@dataclass
class Event:
    ts: datetime
    type: EventType
    payload: dict[str, Any] | Any
```

### 6. Create [domain/config.py](src/domain/config.py) or [engine/config.py](src/engine/config.py)

`BacktestConfig` — typed, serializable. References `DataProviderConfig` from loader or paths.

### 7. Update [domain/**init**.py](src/domain/__init__.py)

Re-export new types.

### 8. Create domain tests

- `src/domain/tests/__init__.py`
- `src/domain/tests/conftest.py` — shared fixtures (sample datetime, sample contract_id)
- `src/domain/tests/test_order.py`
- `src/domain/tests/test_fill.py`
- `src/domain/tests/test_position.py`
- `src/domain/tests/test_portfolio.py`
- `src/domain/tests/test_event.py`
- `src/domain/tests/test_config.py`
- Update `pyproject.toml` testpaths

## Placement

- Domain objects: `src/domain/` (alongside bars, quotes, contract, snapshot)
- BacktestConfig: Either `domain/config.py` (if purely data) or new `src/engine/` package with `config.py` (if engine will grow). Recommend `domain/config.py` for now; engine can import it.

## Tests

**Location:** `src/domain/tests/` (new package) or `src/loader/tests/` (domain tests currently live in loader). Recommend `src/domain/tests/` for domain-only types, or keep alongside existing loader tests in `src/loader/tests/` since loader already tests domain types. **Decision:** Add `src/domain/tests/` — domain objects are independent of loader.

**Framework:** pytest. Follow conventions from [011_m1_dataprovider_test_plan.md](planning/011_m1_dataprovider_test_plan.md).

### test_order.py — Order


| ID  | Test                                                                     | Expected                              |
| --- | ------------------------------------------------------------------------ | ------------------------------------- |
| O1  | Create Order with id, ts, instrument_id, side, qty, order_type           | All fields populated                  |
| O2  | Order is immutable (frozen dataclass)                                    | Assignment to field raises            |
| O3  | Order with limit order_type has limit_price; market has limit_price=None | Correct default                       |
| O4  | tif defaults to "GTC"                                                    | tif == "GTC"                          |
| O5  | side is "BUY" or "SELL"; qty is positive                                 | Validation (or documented convention) |
| O6  | instrument_id accepts contract_id format and symbol                      | Stable string                         |


### test_fill.py — Fill


| ID  | Test                                                | Expected                  |
| --- | --------------------------------------------------- | ------------------------- |
| F1  | Create Fill with order_id, ts, fill_price, fill_qty | All required fields       |
| F2  | fees defaults to 0.0; liquidity_flag optional       | Optional fields           |
| F3  | fill_qty is positive; fill_price is positive        | Sanity                    |
| F4  | Fill references valid order_id (string)             | order_id is stable string |


### test_position.py — Position


| ID  | Test                                                                            | Expected          |
| --- | ------------------------------------------------------------------------------- | ----------------- |
| P1  | Create Position with instrument_id, qty, avg_price, multiplier, instrument_type | All fields set    |
| P2  | qty can be negative (short position)                                            | Short supported   |
| P3  | qty == 0 is valid (closed position)                                             | Edge case         |
| P4  | instrument_type is "option" or "underlying"                                     | Documented values |
| P5  | multiplier is positive (e.g. 100 for standard options)                          | Positive          |


### test_portfolio.py — PortfolioState


| ID  | Test                                                                             | Expected   |
| --- | -------------------------------------------------------------------------------- | ---------- |
| PS1 | Create PortfolioState with cash, positions, realized_pnl, unrealized_pnl, equity | All fields |
| PS2 | positions is dict[str, Position]; empty dict valid                               | Structure  |
| PS3 | **Invariant:** equity == cash + sum(mark_value(positions)) within tolerance      | 000 §6     |
| PS4 | No NaN in cash, equity, pnl fields                                               | 000 §6     |
| PS5 | Position quantities are integers (contracts)                                     | 000 §6     |


### test_event.py — Event


| ID  | Test                                                       | Expected            |
| --- | ---------------------------------------------------------- | ------------------- |
| E1  | Create Event with ts, type (EventType), payload            | All fields          |
| E2  | EventType has MARKET, ORDER, FILL, LIFECYCLE               | Enum values         |
| E3  | payload can be dict or object (Order, Fill, etc.)          | Flexible            |
| E4  | Event is serializable for logs (ts, type, payload to dict) | Run manifest / logs |


### test_config.py — BacktestConfig


| ID  | Test                                                            | Expected             |
| --- | --------------------------------------------------------------- | -------------------- |
| BC1 | Create BacktestConfig with symbol, start, end, timeframe_base   | Required fields      |
| BC2 | seed is int or None; None = no stochastic                       | Optional             |
| BC3 | data_provider_config references DataProviderConfig or paths     | Integration point    |
| BC4 | Config is serializable (to dict, to JSON)                       | Run manifest         |
| BC5 | Round-trip: config -> dict -> config reproduces same run params | Determinism          |
| BC6 | timeframe_base in ["1d", "1h", "1m"]                            | MVP supported values |


### Test Infrastructure

- Add `src/domain/tests/__init__.py` and `src/domain/tests/conftest.py` (shared fixtures: sample datetime, sample contract_id).
- Update `pyproject.toml` testpaths to include `src/domain/tests`.

## Outcome

- All canonical domain objects from 000 §3 implemented
- BacktestConfig ready for Clock/Portfolio/Broker/Reporter to consume
- Step 2 (Clock) can proceed with `BacktestConfig.start`, `.end`, `.timeframe_base`
