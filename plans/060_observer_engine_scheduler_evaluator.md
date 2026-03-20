---
name: 060 Engine Scheduler Evaluator
overview: "Implement the engine: bar-close evaluation scheduler, strategy runner, CandidateStore with validity windows and invalidation, deduplication. Test-first."
todos: []
isProject: false
---

# 060: Engine (Scheduler + Evaluator + Candidate Store)

Conforms to [000_observer_mvp_initial_plan.md](000_observer_mvp_initial_plan.md) §engine/.

---

## Project Practice: Test-First (Red-Green-Refactor)

| Stage | Description |
|-------|--------------|
| **Red** | Write failing tests that specify the expected behavior. Run tests; they fail. |
| **Green** | Implement minimal code to make the tests pass. Run tests; they pass. |
| **Refactor** | Clean up implementation while keeping tests green. |

---

## Objective

Build the engine that orchestrates strategy evaluation. The engine:
1. Decides **when** to evaluate (bar-close cadence)
2. **Runs** all enabled strategies
3. **Stores** resulting candidates with validity windows
4. **Deduplicates** and **invalidates** expired candidates

---

## Existing Foundation

- Step 020: canonical types (TradeCandidate) in `core/`
- Step 030: BaseProvider + SimProvider in `providers/`
- Step 040: MarketState + Context in `state/`
- Step 050: BaseStrategy + DummyStrategy in `strategies/`

---

## Interface Contract

### Engine

```python
class Engine:
    """Orchestrates strategy evaluation on bar-close events.

    Reasoning: Strategies should not manage their own scheduling. The engine
    centralizes timing, runs strategies, and manages the candidate lifecycle.
    Engine owns state updates — on_bar both updates MarketState and triggers
    evaluation when the timeframe matches.
    """

    def __init__(self, strategies: list[BaseStrategy], state: MarketState, config: EngineConfig) -> None: ...

    def on_bar(self, bar: Bar) -> list[TradeCandidate]:
        """Update MarketState with bar, then trigger evaluation if bar matches
        eval_timeframe. Returns new candidates (empty list if no evaluation)."""

    def evaluate(self, timestamp: datetime | None = None) -> list[TradeCandidate]:
        """Run all enabled strategies against current Context. Returns new candidates.
        timestamp defaults to datetime.now(UTC); engine passes bar.timestamp
        for deterministic evaluation (per 040 design)."""

    def get_active_candidates(self, now: datetime | None = None) -> list[TradeCandidate]:
        """Return all non-expired candidates. now defaults to datetime.now(UTC)."""

    def invalidate_expired(self, now: datetime | None = None) -> list[TradeCandidate]:
        """Remove and return candidates past their valid_until. now defaults to datetime.now(UTC)."""
```

#### State update ownership

`Engine.on_bar(bar)` calls `state.update_bar(bar)` internally, then checks whether the bar's timeframe matches `config.eval_timeframe`. This makes the engine self-contained: feed it bars and it drives the full pipeline. Tests only need to construct an Engine and call `on_bar()`.

#### Synchronous design

Strategies are pure logic (`evaluate(ctx) -> list[TradeCandidate]`), and `MarketState.get_context()` is synchronous. Nothing in the engine pipeline requires I/O, so `on_bar`, `evaluate`, `get_active_candidates`, and `invalidate_expired` are all **synchronous**. The async integration layer (step 070) calls these sync methods from within the event loop.

### EngineConfig

```python
@dataclass(frozen=True)
class EngineConfig:
    eval_timeframe: str = "5m"     # bar timeframe that triggers evaluation
```

Note: `max_candidates_per_strategy` deferred to step 130 (ranking/throttling). Not needed for the core engine loop.

### CandidateStore

```python
class CandidateStore:
    """Stores trade candidates with validity tracking and deduplication.

    Reasoning: Candidates have a lifecycle — they're created, active for a window,
    then expire. The store manages this lifecycle centrally.
    """

    def add(self, candidates: list[TradeCandidate]) -> list[TradeCandidate]:
        """Deduplicate against existing active candidates (by symbol+strategy+direction),
        then store. Returns the candidates actually added (post-dedup).
        Replace semantics: a new candidate with the same dedup key replaces the old one."""

    def get_active(self, now: datetime | None = None) -> list[TradeCandidate]:
        """Return all non-expired candidates. now defaults to datetime.now(UTC)."""

    def invalidate_expired(self, now: datetime) -> list[TradeCandidate]:
        """Remove and return candidates past their valid_until."""
```

#### Deduplication semantics

Deduplication key: `(symbol, strategy, direction)`. **Replace semantics**: when `add()` receives a candidate whose key matches an already-active candidate, the old one is removed and the new one is stored. This reflects the latest market evaluation. Dedup is rolled into `add()` — no separate `deduplicate()` call needed.

---

## Module Layout

```
backend/src/engine/
  __init__.py           # re-exports Engine, EngineConfig, CandidateStore
  engine.py             # Engine class
  candidate_store.py    # CandidateStore
  config.py             # EngineConfig

backend/tests/unit/engine/
  __init__.py
  conftest.py           # fixtures: engine with DummyStrategy, pre-populated state
  test_engine.py
  test_candidate_store.py
  test_config.py
```

---

## Implementation Phases

### Phase 0: Directory setup

| Stage | Tasks |
|-------|-------|
| **Setup** | Create `backend/src/engine/` with `__init__.py`. Create `backend/tests/unit/engine/` with `__init__.py`. |

### Phase 1: EngineConfig

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: EngineConfig creation with defaults; eval_timeframe and max_candidates_per_strategy accessible |
| **Green** | Implement `config.py`: EngineConfig frozen dataclass |
| **Refactor** | Minimal — single dataclass |

### Phase 2: CandidateStore

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_candidate_store.py`: add stores candidates and returns them; get_active(now=...) returns non-expired only; invalidate_expired(now) removes past valid_until and returns them; add with same dedup key (symbol+strategy+direction) replaces existing candidate; add with different key appends |
| **Green** | Implement `candidate_store.py`: internal list, add (with replace-dedup), get_active (filter by valid_until > now), invalidate_expired |
| **Refactor** | Consider indexing by symbol or strategy for performance |

### Phase 3: Engine — evaluation trigger + state update

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_engine.py`: on_bar with matching timeframe calls evaluate and returns candidates; on_bar with non-matching timeframe returns empty list and does not evaluate; on_bar updates MarketState (bar appears in state after call); evaluate(timestamp=...) passes timestamp to get_context |
| **Green** | Implement `engine.py`: on_bar calls state.update_bar(bar), checks bar.timeframe against config.eval_timeframe, calls evaluate(timestamp=bar.timestamp); evaluate gets Context from state with timestamp, runs each strategy sequentially |
| **Refactor** | Extract strategy runner logic |

### Phase 4: Engine — full lifecycle

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: evaluate returns new candidates and adds to CandidateStore; get_active_candidates(now=...) delegates to CandidateStore; invalidate_expired(now=...) cleans up; end-to-end with DummyStrategy: on_bar(bar) -> candidates appear in get_active_candidates -> advance time past valid_until -> invalidate_expired removes them |
| **Green** | Wire Engine to CandidateStore; implement get_active_candidates, invalidate_expired (both accept optional now parameter) |
| **Refactor** | Clean separation of concerns |

---

## Data Flow

```
Bar arrives (from provider async stream)
  -> Engine.on_bar(bar)
    -> state.update_bar(bar)
    -> if bar.timeframe == config.eval_timeframe:
      -> Context = state.get_context(timestamp=bar.timestamp)
      -> for strategy in strategies:
        -> candidates = strategy.evaluate(Context)
        -> CandidateStore.add(candidates)   # dedup + replace built in
      -> CandidateStore.invalidate_expired(bar.timestamp)
      -> return all new candidates
    -> else: return []

API layer (step 070) calls on_bar from async context, then pushes
candidates over WebSocket if any were returned.
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Evaluation trigger | Bar close on configurable timeframe | 000 recommends bar-close cadence; avoids noise from tick-level eval |
| State update ownership | Engine.on_bar updates MarketState | Engine is self-contained; tests only call on_bar. Integration layer just feeds bars. |
| Synchronous engine | on_bar, evaluate, get_active_candidates all sync | No I/O inside engine; strategies are pure logic. Async integration layer (070) calls sync engine. |
| Timestamp pass-through | evaluate(timestamp=bar.timestamp) → get_context(timestamp) | Deterministic evaluation per 040 design. Tests pass explicit timestamps. |
| Deduplication key | symbol + strategy + direction | Same setup from same strategy shouldn't flood candidates |
| Dedup semantics | Replace: new candidate replaces old with same key | Latest evaluation reflects current market; stale candidates should not persist |
| Dedup rolled into add() | No separate deduplicate() method | Single call site; impossible to forget dedup step |
| Expiration sweep | On every evaluation cycle | Natural cadence; no separate timer needed |
| Strategy execution | Sequential (not parallel) | Simpler; strategies are fast (pure logic); parallelize later if needed |
| now parameters | Optional on get_active_candidates, invalidate_expired | Testability: tests pass explicit time; production defaults to UTC now |
| Test location | `backend/tests/unit/engine/` | Consistent with steps 020–050. Tests outside source package. |
| `from __future__ import annotations` | All source files | Consistent with project convention. |

---

## Acceptance Criteria

- [ ] `EngineConfig` holds eval_timeframe
- [ ] `CandidateStore` stores, retrieves active, invalidates expired, deduplicates (replace semantics)
- [ ] `Engine.on_bar()` updates MarketState and triggers evaluation only when timeframe matches
- [ ] `Engine.evaluate(timestamp=...)` runs all strategies with deterministic Context timestamp
- [ ] `Engine.get_active_candidates(now=...)` returns non-expired candidates
- [ ] `Engine.invalidate_expired(now=...)` removes and returns expired candidates
- [ ] End-to-end: on_bar(bar) -> candidates appear -> advance time -> candidates expire
- [ ] Unit tests pass: `pytest backend/tests/unit/engine/`

---

## Out of Scope

- Ranking / scoring normalization (step 130)
- Per-strategy throttling / max_candidates_per_strategy (step 130)
- Multi-timeframe evaluation (evaluate at both 1m and 5m bar close)
- Notification/callback system for WebSocket push (handled by step 070 calling on_bar and inspecting return value)
- Async engine methods (strategies are sync; async boundary lives in step 070)
