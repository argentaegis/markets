---
name: 050 Strategy Interface + DummyStrategy
overview: "Define BaseStrategy ABC, Requirements, and Context contract. Implement DummyStrategy that emits a sample TradeCandidate. Test-first."
todos: []
isProject: false
---

# 050: Strategy Interface + DummyStrategy

Conforms to [000_observer_mvp_initial_plan.md](000_observer_mvp_initial_plan.md) §strategies/ and §Canonical interfaces — Strategy interface.

---

## Project Practice: Test-First (Red-Green-Refactor)

| Stage | Description |
|-------|--------------|
| **Red** | Write failing tests that specify the expected behavior. Run tests; they fail. |
| **Green** | Implement minimal code to make the tests pass. Run tests; they pass. |
| **Refactor** | Clean up implementation while keeping tests green. |

---

## Objective

Define the strategy interface that all user strategies must implement, then build `DummyStrategy` — a trivial strategy that always emits one sample TradeCandidate. This validates the interface and provides a concrete implementation for wiring the engine (step 060) and testing the full pipeline.

---

## Existing Foundation

- Step 010: folder structure, `backend/src/strategies/` package
- Step 020: canonical types (TradeCandidate, Direction, EntryType, FutureSymbol) in `core/`
- Step 040: Context defined in `state/` (**hard dependency** — 050 cannot run before 040)

---

## Interface Contract

### BaseStrategy (from 000 §Strategy interface)

```python
class BaseStrategy(ABC):
    """Base class for all user strategies.

    Reasoning: Strategies are pure logic — they read from Context and emit
    TradeCandidate[]. No direct API calls. No state mutation.
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def requirements(self) -> Requirements: ...

    @abstractmethod
    def evaluate(self, ctx: Context) -> list[TradeCandidate]: ...
```

### Requirements

```python
@dataclass(frozen=True)
class Requirements:
    """Declares what data a strategy needs from the market state.

    Reasoning: The engine uses this to verify the strategy has sufficient data
    before calling evaluate(). Prevents strategies from failing on missing data.
    """

    symbols: list[str]          # canonical symbols (e.g. ["ESH26"]) per 020 convention
    timeframes: list[str]       # e.g., ["5m", "1m"]
    lookback: int               # number of bars needed per timeframe
    needs_quotes: bool = False  # whether real-time quotes are needed
```

### Strategy Rules (from 000)

- Strategies are pure logic; no direct API calls
- Strategies read from Context (read-only), emit `list[TradeCandidate]`
- Strategies can be added without touching engine code (dynamic loading in step 120)

---

## Module Layout

```
backend/src/strategies/
  __init__.py           # re-exports BaseStrategy, Requirements, DummyStrategy
  base.py               # BaseStrategy ABC, Requirements
  dummy_strategy.py     # DummyStrategy implementation

backend/tests/unit/strategies/
  __init__.py
  conftest.py           # fixtures: sample Context, expected candidates
  test_base.py          # protocol compliance
  test_dummy_strategy.py
```

---

## DummyStrategy Behavior

- `name` = "dummy"
- `requirements()`: watches `["ESH26"]`, timeframe `["5m"]`, lookback 1, needs_quotes=False
- `evaluate(ctx)`: returns one TradeCandidate when bar data is available:
  - id = generated UUID (`str(uuid.uuid4())`)
  - symbol = "ESH26"
  - strategy = self.name (i.e., "dummy")
  - direction = LONG
  - entry_type = LIMIT
  - entry_price = last bar's close
  - stop_price = entry_price - 2.0
  - targets = [entry_price + 2.0, entry_price + 4.0]
  - score = 50.0
  - explain = ["Dummy strategy", "Always generates a sample candidate", "For testing only"]
  - valid_until = ctx.timestamp + timedelta(minutes=5)
  - tags = {"strategy": "dummy", "setup": "test"}
  - created_at = ctx.timestamp
- Returns `[]` when no bars are available for required symbol/timeframe

---

## Implementation Phases

### Phase 0: Test directory setup

| Stage | Tasks |
|-------|-------|
| **Setup** | Create `backend/tests/unit/strategies/` with `__init__.py`. |

### Phase 1: BaseStrategy + Requirements

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_base.py`: BaseStrategy is abstract (cannot instantiate); BaseStrategy has 3 abstract members (name, requirements, evaluate); Requirements creation with all fields; Requirements is frozen |
| **Green** | Implement `base.py`: BaseStrategy ABC, Requirements frozen dataclass |
| **Refactor** | Ensure re-exports from `__init__.py` with `__all__` (BaseStrategy, Requirements initially; DummyStrategy added after Phase 2) |

### Phase 2: DummyStrategy

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_dummy_strategy.py`: DummyStrategy implements BaseStrategy; name is "dummy"; requirements returns correct Requirements with `symbols=["ESH26"]`; evaluate with a sample Context (containing ESH26 5m bars) returns exactly one TradeCandidate; assert symbol="ESH26", strategy="dummy", direction=LONG, entry_type=LIMIT; entry_price equals last bar's close; stop_price = entry - 2.0; targets = [entry + 2.0, entry + 4.0]; score = 50.0; valid_until = ctx.timestamp + 5 min; id is a valid non-empty string (UUID not deterministic — do not assert exact value) |
| **Green** | Implement `dummy_strategy.py`: DummyStrategy class using `uuid.uuid4()` for candidate id, `strategy=self.name` |
| **Refactor** | Verify TradeCandidate fields match 000 §TradeCandidate schema |

### Phase 3: Edge cases

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: evaluate with empty bar window returns empty list (no data = no candidate); evaluate with Context missing required symbol returns empty list; evaluate with Context that has the symbol but no bars for required timeframe returns empty list |
| **Green** | Add guard clauses to DummyStrategy.evaluate |
| **Refactor** | Document the "no data = no candidates" convention |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Strategy purity | No side effects; read Context, return candidates | 000 requirement; testable, deterministic |
| Requirements declaration | Upfront via requirements() method | Engine can pre-check data availability before evaluate() |
| DummyStrategy always emits | Returns candidate when data is present | Validates full pipeline without real market logic |
| Empty return on missing data | Return `[]` instead of raising | Graceful degradation; engine logs absence |
| Symbol convention | `"ESH26"` not `"ES"` | Matches step 020 canonical symbol format (`{root}{contract_code}`). Must match MarketState keys and SimProvider output. |
| TradeCandidate.strategy | `self.name` | Links candidate back to the strategy that produced it. Must match `BaseStrategy.name`. |
| TradeCandidate.id | `uuid.uuid4()` per call | Unique identification for deduplication/journaling. Not deterministic — tests assert format/presence, not exact value. |
| Test location | `backend/tests/unit/strategies/` | Consistent with steps 020/030. Tests outside source package. |
| `from __future__ import annotations` | All source files | Consistent with project convention. |

---

## Acceptance Criteria

- [ ] `BaseStrategy` ABC defined with `name`, `requirements()`, `evaluate(ctx)`
- [ ] `Requirements` frozen dataclass with symbols, timeframes, lookback, needs_quotes
- [ ] `DummyStrategy` implements `BaseStrategy`
- [ ] `DummyStrategy.name` is `"dummy"`
- [ ] `DummyStrategy.requirements()` uses canonical symbol `"ESH26"`
- [ ] `DummyStrategy.evaluate()` returns a valid `TradeCandidate` list when data present (strategy="dummy", correct prices, valid_until, etc.)
- [ ] `DummyStrategy.evaluate()` returns empty list when required data is missing
- [ ] TradeCandidate fields match 000 §TradeCandidate schema (including `strategy` field)
- [ ] `DummyStrategy` re-exported from `strategies/__init__.py`
- [ ] Unit tests pass: `pytest backend/tests/unit/strategies/`

---

## Out of Scope

- Real strategy logic (ORB = step 110)
- Dynamic loading / registry (step 120)
- Per-strategy configuration from config.yaml (step 120)
- Strategy-level logging or telemetry
