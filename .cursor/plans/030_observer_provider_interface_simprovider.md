---
name: 030 Provider Interface + SimProvider
overview: "Define BaseProvider protocol and implement SimProvider emitting fake Quote + Bar async streams. Scaffold stubs for future provider sources. Test-first."
todos: []
isProject: false
---

# 030: Provider Interface + SimProvider

Conforms to [000_observer_mvp_initial_plan.md](000_observer_mvp_initial_plan.md) §providers/.

---

## Project Practice: Test-First (Red-Green-Refactor)

| Stage | Description |
|-------|--------------|
| **Red** | Write failing tests that specify the expected behavior. Run tests; they fail. |
| **Green** | Implement minimal code to make the tests pass. Run tests; they pass. |
| **Refactor** | Clean up implementation while keeping tests green. |

---

## Objective

Define the `BaseProvider` protocol that all data sources must implement, then build `SimProvider` — a fake data provider that emits realistic Quote and Bar streams for development and testing. This is the foundation for all data ingestion; real providers (Schwab, etc.) will implement the same interface later.

---

## Existing Foundation

- Step 010: folder structure exists, `backend/src/providers/` package
- Step 020: canonical types (Quote, Bar, FutureSymbol, ContractSpec, TradingSession, DataQuality) defined in `core/`

---

## Interface Contract

### BaseProvider (abstract protocol)

```python
class BaseProvider(ABC):
    """Base protocol for all market data providers.

    Reasoning: All providers must emit canonical types only. No vendor objects
    leak past this layer. Providers wrap exceptions and report health.
    """

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def subscribe_quotes(self, symbols: list[str]) -> AsyncIterator[Quote]: ...

    @abstractmethod
    async def subscribe_bars(self, symbols: list[str], timeframe: str) -> AsyncIterator[Bar]: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def health(self) -> ProviderHealth: ...

    @abstractmethod
    def get_contract_specs(self) -> dict[str, ContractSpec]: ...
```

### ProviderHealth

```python
@dataclass(frozen=True)
class ProviderHealth:
    connected: bool
    source: str
    last_heartbeat: datetime | None
    message: str
```

### Provider Rules (from 000)

- Providers emit only canonical types (Quote, Bar)
- Attach `source` to every emitted event
- Attach `quality` flag (DataQuality) to every event
- Never throw raw exceptions to engine; wrap and report via health()
- Providers own their instrument metadata via `get_contract_specs()`

---

## Module Layout

```
backend/src/providers/
  __init__.py           # re-exports BaseProvider, ProviderHealth, SimProvider
  base.py               # BaseProvider ABC, ProviderHealth
  sim_provider.py       # SimProvider implementation

backend/tests/unit/providers/
  __init__.py
  conftest.py           # shared fixtures (symbols, contract specs)
  test_base.py          # protocol compliance tests
  test_sim_provider.py
```

---

## SimProvider Constructor

```python
class SimProvider(BaseProvider):
    """Fake market data provider for development and testing.

    Reasoning: Deterministic seeded random-walk price generator. Emits
    canonical Quote/Bar streams at configurable intervals. Allows the
    full pipeline (provider -> state -> engine -> API) to run without
    a real brokerage connection.
    """

    def __init__(
        self,
        symbols: list[str] | None = None,          # default: ["ESH26", "NQM26"]
        base_prices: dict[str, float] | None = None,  # default: {"ESH26": 5400.0, "NQM26": 19500.0}
        quote_interval: float = 0.1,                # seconds between quotes (0 for tests)
        bar_interval: float = 60.0,                 # seconds between bars
        seed: int = 42,
    ) -> None: ...
```

### SimProvider Behavior

- Default symbols: `["ESH26", "NQM26"]`
- Default base prices: `{"ESH26": 5400.0, "NQM26": 19500.0}`
- Emits quotes at `quote_interval` seconds (use `quote_interval=0` in tests for immediate yields)
- Emits bars at `bar_interval` seconds (independent random walk OHLCV generation)
- Prices walk randomly using seeded RNG (`random.Random(seed)`) for determinism
- All emitted Quote/Bar objects use canonical types with `source="sim"` and `quality=DataQuality.OK`
- `connect()` sets `_connected = True`; `disconnect()` sets `_connected = False` and stops generators
- Generators check `_connected` each iteration; return cleanly when False
- `health()` reports connection state with `source="sim"`
- `get_contract_specs()` returns hardcoded specs for configured symbols:
  - ESH26: tick_size=0.25, point_value=50.0, ES_RTH session (9:30-16:00 ET)
  - NQM26: tick_size=0.25, point_value=20.0, NQ_RTH session (9:30-16:00 ET)

#### Test timing

Tests should use `quote_interval=0` and `bar_interval=0` so generators yield without delay. Collect a fixed count of items and break out of the `async for` loop. This prevents flaky or slow tests.

---

## Implementation Phases

### Phase 0: Test directory setup

| Stage | Tasks |
|-------|-------|
| **Setup** | Create `backend/tests/unit/providers/` with `__init__.py`. |

### Phase 1: BaseProvider protocol + ProviderHealth

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_base.py`: verify BaseProvider is abstract (cannot instantiate); ProviderHealth creation and fields; BaseProvider defines all 6 methods (connect, subscribe_quotes, subscribe_bars, disconnect, health, get_contract_specs) |
| **Green** | Implement `base.py`: BaseProvider ABC with abstract methods; ProviderHealth frozen dataclass |
| **Refactor** | Ensure re-exports from `__init__.py` with `__all__` |

### Phase 2: SimProvider — quote stream

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_sim_provider.py`: SimProvider implements BaseProvider; connect/disconnect lifecycle; subscribe_quotes yields Quote objects with correct fields (use `quote_interval=0`); prices vary but stay near base; source="sim"; quality=OK; determinism with same seed produces identical output |
| **Green** | Implement `sim_provider.py`: SimProvider with seeded random price walk, async quote generator, `_connected` flag |
| **Refactor** | Extract price walk logic into helper function |

### Phase 3: SimProvider — bar stream + contract specs

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: subscribe_bars yields Bar objects (use `bar_interval=0`); OHLCV values are consistent (high >= open, close, low; low <= all); timestamp is UTC; timeframe matches subscription; get_contract_specs returns specs for configured symbols with correct tick_size and point_value |
| **Green** | Implement bar generation (independent random walk); implement get_contract_specs with hardcoded ES/NQ specs |
| **Refactor** | Configurable base prices; clean up spec construction |

### Phase 4: Health + disconnect lifecycle

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: health() before connect shows not connected; after connect shows connected; after disconnect shows not connected; generators stop yielding after disconnect() |
| **Green** | Implement health tracking; generator cleanup on disconnect |
| **Refactor** | Clean up lifecycle state management |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Async iterators for streams | `AsyncIterator[Quote]`, `AsyncIterator[Bar]` | Natural fit for streaming data; works with `async for` |
| Seeded RNG in SimProvider | Configurable seed parameter | Determinism for tests; reproducible dev scenarios |
| Source field | String "sim" on all emitted events | Distinguishes simulated from real data throughout the system |
| Price generation | Random walk near base price | Simple, realistic enough for UI dev; not modeling actual market microstructure |
| ContractSpec on provider | `get_contract_specs()` method on BaseProvider | Providers own their instrument metadata. SimProvider hardcodes specs; SchwabProvider (step 100) derives them from stream fields (TICK, FUTURE_MULTIPLIER, TRADING_HOURS). Consumers (engine, strategies) get specs through the provider. |
| Disconnect stops generators | `_connected` flag checked each iteration | Clean shutdown; generators return when flag is False. No orphaned coroutines. |
| Test intervals | `quote_interval=0`, `bar_interval=0` for tests | Prevents flaky/slow tests. Generators yield immediately without sleep. |
| Test location | `backend/tests/unit/providers/` | Consistent with step 020 convention. Tests outside source package. |

---

## Acceptance Criteria

- [ ] `BaseProvider` ABC defined with all 6 methods (5 from 000 §Provider interface + `get_contract_specs`)
- [ ] `ProviderHealth` frozen dataclass defined
- [ ] `SimProvider` implements `BaseProvider`
- [ ] `subscribe_quotes` yields `Quote` objects with realistic prices
- [ ] `subscribe_bars` yields `Bar` objects with valid OHLCV (high >= open/close/low, low <= all)
- [ ] All emitted events have source="sim" and quality=DataQuality.OK
- [ ] Deterministic output with same seed
- [ ] `health()` correctly reflects connection state
- [ ] `get_contract_specs()` returns ContractSpec for each configured symbol
- [ ] Generators stop after `disconnect()`
- [ ] No vendor/raw types leak past provider (only canonical core types)
- [ ] Unit tests pass: `pytest backend/tests/unit/providers/`

---

## Out of Scope

- Real provider implementations (Schwab = step 100)
- Replay from historical files (may be added to SimProvider later)
- Multi-provider aggregation
- Rate limiting or throttling
- Multiple simultaneous subscriptions to the same stream (V1 single-consumer)
