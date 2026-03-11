---
name: 020 Core Canonical Types
overview: "Define all canonical domain types in core/: Instrument, FutureSymbol, ContractSpec, Quote, Bar, DataQuality, TradeCandidate, and tick-size normalization. Test-first."
todos: []
isProject: false
---

# 020: Core Canonical Types (`core/` module)

Conforms to [000_observer_mvp_initial_plan.md](000_observer_mvp_initial_plan.md) §core/ and §Futures-specific requirements.

---

## Project Practice: Test-First (Red-Green-Refactor)

| Stage | Description |
|-------|--------------|
| **Red** | Write failing tests that specify the expected behavior. Run tests; they fail. |
| **Green** | Implement minimal code to make the tests pass. Run tests; they pass. |
| **Refactor** | Clean up implementation while keeping tests green. |

---

## Objective

Define the canonical domain types used everywhere in the system. These types form the contract between all modules. No module may use vendor-specific or raw types across boundaries — only core types.

---

## Existing Foundation

- Step 010 complete: folder structure exists, `backend/src/core/` package with `__init__.py`

---

## Target Domain Types

### Instrument identity

| Type | Fields | Notes |
|------|--------|-------|
| `InstrumentType` | Enum: FUTURE, EQUITY, OPTION | Asset class discriminator |
| `FutureSymbol` | root (str), contract_code (str), front_month_alias (str) | e.g., root="ES", contract_code="H26", alias="ES1!". `to_symbol() -> str` returns `"{root}{contract_code}"` (e.g. `"ESH26"`) |
| `ContractSpec` | symbol (str), instrument_type (InstrumentType), tick_size (float), point_value (float), session (TradingSession) | `symbol` is the canonical symbol string (e.g. `"ESH26"`, matching `FutureSymbol.to_symbol()`) |
| `TradingSession` | name (str), start_time (time), end_time (time), timezone (str) | RTH vs ETH session definitions. V1: RTH sessions only (no midnight crossing). Includes `contains(t: time) -> bool` helper. |

#### Symbol convention

The canonical symbol string is `"{root}{contract_code}"` (e.g. `"ESH26"`). This string is used as the key in `ContractSpec.symbol`, `Quote.symbol`, `Bar.symbol`, `TradeCandidate.symbol`, and `MarketState` lookups. `FutureSymbol.to_symbol()` produces this string. `FutureSymbol.front_month_alias` (e.g. `"ES1!"`) is for display and provider mapping only.

#### TradingSession V1 limitation

V1 supports sessions where `start_time < end_time` (no midnight crossing). This covers RTH (9:30 AM – 4:00 PM ET). ETH sessions that cross midnight (e.g. 6:00 PM – 5:00 PM next day) require a `crosses_midnight` extension — deferred to v2 or when ETH strategies are added.

### Market data

| Type | Fields | Notes |
|------|--------|-------|
| `Quote` | symbol (str), bid (float), ask (float), last (float), bid_size (int), ask_size (int), volume (int), timestamp (datetime), source (str), quality (DataQuality) | Real-time quote snapshot. `__post_init__` rejects NaN bid/ask/last and negative sizes/volume. |
| `Bar` | symbol (str), timeframe (str), open (float), high (float), low (float), close (float), volume (int), timestamp (datetime), source (str), quality (DataQuality) | OHLCV bar; timestamp = bar close time (UTC). `__post_init__` rejects NaN prices and negative volume. |
| `DataQuality` | Enum: OK, STALE, MISSING, PARTIAL | Quality flags attached to every data point |

### Recommendations

| Type | Fields | Notes |
|------|--------|-------|
| `Direction` | Enum: LONG, SHORT | Trade direction |
| `EntryType` | Enum: MARKET, LIMIT, STOP | How to enter |
| `TradeCandidate` | id (str), symbol (str), strategy (str), direction (Direction), entry_type (EntryType), entry_price (float), stop_price (float), targets (list[float]), score (float), explain (list[str]), valid_until (datetime), tags (dict[str, str]), created_at (datetime) | The recommendation artifact; informational only. `score` is unconstrained float (normalization to 0-100 is step 130). `explain` accepts any list[str] (3-6 guideline enforced by strategies, not the type). |

### Utilities

| Function | Signature | Purpose |
|----------|-----------|---------|
| `normalize_price` | `(price: float, tick_size: float) -> float` | Round price to nearest tick. Uses `Decimal` internally for precision, returns `float`. |
| `ticks_between` | `(price_a: float, price_b: float, tick_size: float) -> int` | Number of ticks between two prices. Uses `Decimal` internally for precision. |

---

## Interface Contract

All types use `dataclass(frozen=True)` for immutability. Prices use `float` (matching backtester convention); tick normalization uses `Decimal` internally for exact arithmetic and converts back to `float` on return. Timestamps are timezone-aware UTC. All source files use `from __future__ import annotations`.

---

## Module Layout

```
backend/src/core/
  __init__.py          # re-exports all public types via __all__
  instrument.py        # InstrumentType, FutureSymbol, ContractSpec, TradingSession
  market_data.py       # Quote, Bar, DataQuality
  candidate.py         # Direction, EntryType, TradeCandidate
  tick.py              # normalize_price, ticks_between

backend/tests/unit/
  __init__.py
  core/
    __init__.py
    conftest.py        # shared fixtures (sample symbols, timestamps, specs)
    test_instrument.py
    test_market_data.py
    test_candidate.py
    test_tick.py
```

---

## Implementation Phases

### Phase 0: Test directory + pyproject.toml

| Stage | Tasks |
|-------|-------|
| **Setup** | Create `backend/tests/unit/` and `backend/tests/unit/core/` with `__init__.py` files. Update `pyproject.toml` testpaths to `["tests/unit", "tests/integration"]`. Add `"unit"` to markers. |

### Phase 1: Instrument identity types

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_instrument.py`: InstrumentType enum values; FutureSymbol creation, immutability, and `to_symbol()` returns `"{root}{contract_code}"`; ContractSpec with tick_size and point_value; TradingSession with RTH hours and `contains()` helper |
| **Green** | Implement `instrument.py`: InstrumentType enum, FutureSymbol dataclass with `to_symbol()`, ContractSpec dataclass, TradingSession dataclass with `contains()` |
| **Refactor** | Ensure `__init__.py` re-exports with `__all__`; verify imports work from `core` package |

### Phase 2: Market data types

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_market_data.py`: Quote creation with all fields; Bar creation; DataQuality enum values; timestamp is UTC; immutability; `__post_init__` rejects NaN prices and negative volume |
| **Green** | Implement `market_data.py`: Quote, Bar, DataQuality with `__post_init__` validation |
| **Refactor** | Shared conftest fixtures for sample quotes and bars |

### Phase 3: TradeCandidate

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_candidate.py`: TradeCandidate with all required fields; Direction and EntryType enums; immutability; explain accepts any list of strings; score accepts any float |
| **Green** | Implement `candidate.py`: Direction, EntryType, TradeCandidate |
| **Refactor** | Verify re-exports in `__init__.py` |

### Phase 4: Tick normalization

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_tick.py`: normalize_price rounds to nearest tick (ES tick_size=0.25: 5412.30 -> 5412.25); ticks_between counts correctly; edge cases (exact tick, zero distance); verify float in, float out |
| **Green** | Implement `tick.py`: normalize_price, ticks_between (Decimal internally, float API) |
| **Refactor** | Verify precision with small tick sizes (e.g. CL tick_size=0.01) |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Price type (domain) | `float` | Matches backtester convention. Providers emit floats; JSON serializes natively. Avoids Decimal friction across every module boundary. |
| Price type (tick math) | `Decimal` internally in `tick.py` | Exact arithmetic for normalize_price / ticks_between where floating-point rounding matters. Converts back to `float` at function boundary. |
| Immutability | `frozen=True` dataclasses | Types are passed across module boundaries; immutability prevents accidental mutation |
| Fail-fast validation | `__post_init__` on Bar, Quote | Matches backtester pattern (BarRow rejects NaN). Catches data corruption at creation, not downstream. |
| Timestamp convention | UTC, timezone-aware | Consistent with backtester; avoids ambiguity across sessions |
| Bar timestamp meaning | Bar close time | Matches backtester convention; strategy evaluates after bar closes |
| TradeCandidate.id | UUID string | Unique identification for deduplication and journaling |
| Symbol convention | `"{root}{contract_code}"` (e.g. `"ESH26"`) | Single canonical key used across all types and state lookups |
| Test location | `backend/tests/unit/core/` | Keeps tests out of source package (not included in wheel). Parallel to `backend/tests/integration/`. Scales as modules grow. |
| Score / explain constraints | Unconstrained at type level | Score normalization (0-100) is step 130. Explain length (3-6) is a strategy guideline, not a type invariant. Avoids test friction. |
| `from __future__ import annotations` | All source files | Consistent with backtester; enables modern type hint syntax |

---

## Acceptance Criteria

- [ ] All domain types defined as frozen dataclasses in `backend/src/core/`
- [ ] InstrumentType, DataQuality, Direction, EntryType enums exist
- [ ] FutureSymbol holds root, contract_code, front_month_alias; `to_symbol()` returns `"{root}{contract_code}"`
- [ ] ContractSpec holds symbol, tick_size, point_value, session
- [ ] TradingSession has `contains(t: time) -> bool` helper
- [ ] Quote and Bar use float prices and UTC timestamps
- [ ] Quote and Bar `__post_init__` reject NaN prices and negative volume
- [ ] TradeCandidate includes all fields from 000 §TradeCandidate schema
- [ ] `normalize_price` rounds to nearest tick correctly (float in, float out)
- [ ] `ticks_between` returns integer tick count
- [ ] All types importable from `core` package via `__all__`
- [ ] Unit tests pass: `pytest backend/tests/unit/core/`
- [ ] pyproject.toml testpaths includes both `tests/unit` and `tests/integration`

---

## Out of Scope

- Options-specific types (v2+)
- ETH sessions that cross midnight (v2+ or when ETH strategies added)
- Serialization to JSON/protobuf (handled at API layer in step 070)
- Score normalization to 0-100 range (step 130)
- Explain length enforcement (strategy-level concern, not type-level)
