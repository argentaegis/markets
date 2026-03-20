---
name: 040 Market State Store
overview: "Implement MarketState class tracking latest quotes and rolling bar windows per symbol/timeframe. Provides read-only Context view for strategies. Test-first."
todos: []
isProject: false
---

# 040: Market State Store

Conforms to [000_observer_mvp_initial_plan.md](000_observer_mvp_initial_plan.md) §state/.

---

## Project Practice: Test-First (Red-Green-Refactor)

| Stage | Description |
|-------|--------------|
| **Red** | Write failing tests that specify the expected behavior. Run tests; they fail. |
| **Green** | Implement minimal code to make the tests pass. Run tests; they pass. |
| **Refactor** | Clean up implementation while keeping tests green. |

---

## Objective

Build the "current truth" store for strategies. `MarketState` holds the latest quote per symbol and rolling bar windows per symbol/timeframe. It exposes a read-only `Context` view that strategies consume — strategies never mutate state directly.

---

## Existing Foundation

- Step 010: folder structure, `backend/src/state/` package
- Step 020: canonical types (Quote, Bar, DataQuality) in `core/`

---

## Interface Contract

### MarketState

```python
class MarketState:
    """Current market truth. Updated by provider events, read by strategies via Context.

    Reasoning: Central store prevents strategies from managing their own state.
    Rolling bar windows allow lookback without unbounded memory.
    """

    def __init__(self, max_window_size: int = 500) -> None: ...

    def update_quote(self, quote: Quote) -> None: ...
    def update_bar(self, bar: Bar) -> None: ...
    def get_latest_quote(self, symbol: str) -> Quote | None: ...
    def get_bars(self, symbol: str, timeframe: str, count: int) -> list[Bar]: ...
    def get_context(self, timestamp: datetime | None = None) -> Context: ...
    def get_snapshot(self, timestamp: datetime | None = None) -> MarketSnapshot: ...
```

#### `get_bars` semantics

Returns up to `count` bars for the given symbol/timeframe, oldest first. If fewer than `count` exist, returns all available. Returns `[]` if no bars for that symbol/timeframe combination.

#### `get_context` / `get_snapshot` timestamp

Both accept an optional `timestamp` parameter. When `None`, defaults to `datetime.now(timezone.utc)`. The engine passes the triggering bar's timestamp for deterministic evaluation. Tests should always pass an explicit timestamp.

### Context (read-only view for strategies)

```python
@dataclass(frozen=True)
class Context:
    """Read-only view of market state passed to strategy.evaluate().

    Reasoning: Strategies must not mutate market state. Context provides
    a frozen snapshot of the data they need.
    """

    timestamp: datetime
    quotes: dict[str, Quote]       # symbol -> latest quote
    bars: dict[str, dict[str, list[Bar]]]  # symbol -> timeframe -> bar list
```

#### Snapshot isolation

`frozen=True` prevents field reassignment, but the `dict` and `list` contents are still mutable in Python. To provide true snapshot isolation, `get_context()` must **shallow-copy all mutable containers** when constructing Context:

- New `dict` of quotes (copy of internal dict)
- New nested `dict[str, dict[str, list[Bar]]]` (copy each inner list)

This ensures that subsequent `update_quote`/`update_bar` calls on MarketState do not affect previously created Context objects. The cost is O(n) in quotes + bars, which is acceptable at bar-close cadence.

### MarketSnapshot (serializable for API)

```python
@dataclass
class MarketSnapshot:
    """Full state snapshot for REST API and persistence."""

    timestamp: datetime
    quotes: dict[str, Quote]
    bars: dict[str, dict[str, list[Bar]]]
```

Same copy semantics as Context. MarketSnapshot is kept as a separate type (not frozen) to allow the API layer to augment it with additional fields if needed.

---

## Module Layout

```
backend/src/state/
  __init__.py           # re-exports MarketState, Context, MarketSnapshot
  market_state.py       # MarketState class
  context.py            # Context, MarketSnapshot

backend/tests/unit/state/
  __init__.py
  conftest.py           # fixtures: sample quotes, bars, pre-populated state
  test_context.py
  test_market_state.py
```

---

## Implementation Phases

### Phase 0: Test directory setup

| Stage | Tasks |
|-------|-------|
| **Setup** | Create `backend/tests/unit/state/` with `__init__.py`. |

### Phase 1: Context and MarketSnapshot types

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_context.py`: Context is frozen (field reassignment raises); MarketSnapshot holds quotes and bars; empty Context has empty dicts |
| **Green** | Implement `context.py`: Context frozen dataclass, MarketSnapshot dataclass |
| **Refactor** | Ensure re-exports from `__init__.py` with `__all__` |

### Phase 2: MarketState — quote tracking

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_market_state.py`: MarketState(max_window_size=...) accepts config; update_quote stores latest; get_latest_quote returns it; updating same symbol replaces previous; unknown symbol returns None |
| **Green** | Implement `market_state.py`: internal dict for quotes, update_quote, get_latest_quote |
| **Refactor** | Clean up constructor |

### Phase 3: MarketState — rolling bar windows

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: update_bar appends; get_bars returns last N bars oldest-first; get_bars with count > available returns all available; get_bars for unknown symbol returns `[]`; window rolls (oldest dropped when exceeding max_window_size); bars organized by symbol+timeframe |
| **Green** | Implement bar storage with `collections.deque(maxlen=max_window_size)` per symbol/timeframe |
| **Refactor** | Verify deque slicing behavior for get_bars |

### Phase 4: Context generation + snapshot isolation

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: get_context returns frozen Context with current quotes and bars; get_context(timestamp=...) uses provided timestamp; get_context(timestamp=None) uses UTC now; get_snapshot returns MarketSnapshot; **snapshot isolation test**: update MarketState after get_context → verify original Context unchanged; same test for get_snapshot |
| **Green** | Implement get_context and get_snapshot with shallow-copy of all mutable containers |
| **Refactor** | Extract copy logic into shared helper |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Bar window size | Configurable via `max_window_size`, default 500 | Enough for most strategy lookbacks without unbounded memory |
| Bar storage | `collections.deque(maxlen=N)` per symbol/timeframe | Automatic eviction of oldest bars; O(1) append |
| Context immutability | Frozen dataclass + shallow-copy of containers | `frozen=True` prevents field reassignment; copied dicts/lists prevent mutation of MarketState internals |
| Snapshot isolation | Copy all mutable containers in get_context/get_snapshot | Subsequent updates to MarketState must not corrupt previously-created Context. Tested explicitly. |
| Context timestamp | Optional parameter, defaults to `datetime.now(UTC)` | Engine passes bar timestamp for deterministic evaluation; tests pass explicit timestamps |
| Quote replacement | Latest quote replaces previous per symbol | Only current state matters; historical quotes not needed in V1 |
| Bar ordering | Chronological (oldest first) | Natural for iteration; `bars[-1]` is most recent |
| get_bars partial return | Returns up to `count` bars, or fewer if not enough | Strategies handle short windows gracefully; no padding or errors |
| Test location | `backend/tests/unit/state/` | Consistent with steps 020/030/050. Tests outside source package. |
| `from __future__ import annotations` | All source files | Consistent with project convention. |

---

## Acceptance Criteria

- [ ] `MarketState(max_window_size=N)` constructor accepts config
- [ ] `MarketState` stores and retrieves latest quote per symbol
- [ ] `MarketState` stores rolling bar windows per symbol/timeframe
- [ ] Bar windows roll correctly at max capacity
- [ ] `get_bars` returns up to `count` bars oldest-first; `[]` for unknown symbol/timeframe
- [ ] `get_context(timestamp=...)` returns frozen `Context` with current state and provided timestamp
- [ ] `get_context()` without timestamp uses UTC now
- [ ] `get_snapshot()` returns serializable `MarketSnapshot`
- [ ] Snapshot isolation: updates to MarketState after get_context/get_snapshot do not affect the returned object
- [ ] Unit tests pass: `pytest backend/tests/unit/state/`

---

## Out of Scope

- Persistence to SQLite/DuckDB (step 090)
- Chain snapshots / greeks (v2+)
- Thread-safe concurrent access (single-threaded event loop in V1; document for later)
- Historical data loading (provider responsibility)
- Deep immutability enforcement (Python limitation; convention + copy is sufficient)
- Helper methods on Context (e.g., `get_bars(symbol, tf)`) — strategies use `ctx.bars.get(symbol, {}).get(tf, [])` pattern
