---
name: 090 State Persistence + Candidate Lifecycle
overview: "Close M1: candidate retention limits. Add optional SQLite persistence for quotes/bars (debugging/replay). Test-first."
todos: []
isProject: false
---

# 090: Candidate Retention + State Persistence

Conforms to [000_observer_mvp_initial_plan.md](000_observer_mvp_initial_plan.md) §state/ and M1 milestone.

---

## Project Practice: Test-First (Red-Green-Refactor)

| Stage | Description |
|-------|--------------|
| **Red** | Write failing tests that specify the expected behavior. Run tests; they fail. |
| **Green** | Implement minimal code to make the tests pass. Run tests; they pass. |
| **Refactor** | Clean up implementation while keeping tests green. |

---

## Objective

Close the M1 milestone gap and add debugging infrastructure:

1. **Candidate retention** — `enforce_retention(max_per_strategy)` on CandidateStore, called after each evaluation cycle. This is the only remaining M1 deliverable ("candidate store retains last N candidates").
2. **State persistence** (optional) — SQLite storage for quotes and bars only, enabling post-session debugging and replay. Off by default; does not affect the hot path when disabled.

### What is already done (not repeated here)

- MarketState stores latest quotes + rolling bars (040)
- Evaluation scheduler triggers on bar close (060)
- Invalidation by timestamp (060 — `invalidate_expired()`)
- UI updates only on bar close (070 — `consume_bars` is the only path that broadcasts `candidates_update`; `consume_quotes` never touches the engine)

### What belongs elsewhere

- **Candidate persistence + journaling** → step 130 (Journal with context snapshots, richer design)
- **UI debounce** → already solved in 070 wiring by design

---

## Existing Foundation

- Step 040: MarketState (in-memory, `update_quote`, `update_bar`)
- Step 060: Engine + CandidateStore (`add`, `get_active`, `invalidate_expired`)
- Step 070: Backend API with WebSocket, `wiring.py` (`consume_quotes`, `consume_bars`)
- Step 080: Frontend UI

---

## Interface Contract

### CandidateStore enhancement

```python
class CandidateStore:
    # Existing methods from step 060, plus:
    def enforce_retention(self, max_per_strategy: int) -> list[TradeCandidate]:
        """Remove oldest candidates exceeding per-strategy limit. Return removed.

        Groups by strategy name. Within each group, keeps the newest
        max_per_strategy candidates (by created_at). Removes and returns
        the rest. Strategies with <= limit candidates are untouched.
        """
```

### EngineConfig extension

```python
@dataclass(frozen=True)
class EngineConfig:
    eval_timeframe: str = "5m"
    max_candidates_per_strategy: int = 10   # new — used by enforce_retention
```

### StateStore (persistence layer)

```python
class StateStore:
    """Optional SQLite persistence for quotes and bars.

    Reasoning: Enables post-session debugging, replay, and inspection
    of what data the engine saw at any point in time. When db_path is
    None, all methods are no-ops (disabled by default).

    Candidate persistence is NOT handled here — that belongs to the
    Journal in step 130, which captures richer context alongside each
    candidate.
    """

    def __init__(self, db_path: str | None = None) -> None: ...
    def save_quote(self, quote: Quote) -> None: ...
    def save_bar(self, bar: Bar) -> None: ...
    def get_quotes(self, symbol: str, since: datetime | None = None) -> list[Quote]: ...
    def get_bars(self, symbol: str, timeframe: str, since: datetime | None = None) -> list[Bar]: ...
    @property
    def enabled(self) -> bool: ...
```

Note: When `db_path is None`, `enabled` returns `False` and save/get methods are no-ops (return `[]`). No SQLite file is created.

---

## Module Layout

```
backend/src/engine/
  candidate_store.py    # enhanced with enforce_retention
  config.py             # enhanced with max_candidates_per_strategy
  engine.py             # updated: call enforce_retention after evaluate

backend/src/state/
  persistence.py        # new — StateStore (SQLite, quotes + bars only)
  __init__.py           # updated: export StateStore

backend/src/api/
  wiring.py             # updated: optional StateStore hooks in consume_quotes/consume_bars

backend/tests/unit/engine/
  test_candidate_store.py  # enhanced with retention tests

backend/tests/unit/state/
  test_persistence.py      # new
```

Note: `MarketState` is **not** modified. Persistence hooks live in `wiring.py` (the async boundary layer), keeping MarketState as a clean synchronous in-memory store.

---

## Implementation Phases

### Phase 0: Directory + file setup (Create+Verify)

| Stage | Tasks |
|-------|-------|
| **Create** | Create `backend/src/state/persistence.py` stub. Create `backend/tests/unit/state/test_persistence.py`. Verify existing tests still pass. |
| **Verify** | `pytest backend/tests/unit/ --collect-only` discovers no errors. |

### Phase 1: Candidate retention limits (M1 gap)

| Stage | Tasks |
|-------|-------|
| **Red** | Add tests in `test_candidate_store.py`: `enforce_retention(max_per_strategy=2)` with 3 candidates from same strategy removes the oldest (by `created_at`); returns removed candidates; different strategies have independent limits; `max_per_strategy=0` removes all; candidates at or under the limit are untouched |
| **Green** | Implement `enforce_retention` on `CandidateStore`: group `_candidates` by `.strategy`, sort each group by `.created_at` descending, keep the first `max_per_strategy`, remove and return the rest |
| **Refactor** | Add `max_candidates_per_strategy: int = 10` to `EngineConfig`. Call `self._store.enforce_retention(self._config.max_candidates_per_strategy)` at the end of `Engine.evaluate()`, after `invalidate_expired`. Update existing `test_config.py` for the new field. |

### Phase 2: SQLite StateStore — schema + save/query (quotes + bars only)

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_persistence.py`: `StateStore(db_path=None)` is disabled (`enabled` is `False`, save is no-op, get returns `[]`). `StateStore(db_path=":memory:")` creates tables; `save_quote` + `get_quotes` round-trip works; `save_bar` + `get_bars` round-trip works; filtering by symbol and `since` works; multiple symbols coexist |
| **Green** | Implement `persistence.py`: `StateStore` with SQLite schema creation (`quotes` and `bars` tables), `save_quote`, `save_bar`, `get_quotes`, `get_bars`. When `db_path is None`, all methods are no-ops. |
| **Refactor** | Add indices on `(symbol, timestamp)` for both tables. Ensure `datetime` fields round-trip correctly as ISO 8601 strings. Export `StateStore` from `state/__init__.py`. |

### Phase 3: Wire persistence into wiring layer

| Stage | Tasks |
|-------|-------|
| **Red** | Write integration test: start app with `StateStore(db_path=":memory:")`, feed quotes + bars through, verify data appears in StateStore queries. Also test: start app with `StateStore(db_path=None)` — no error, no writes. |
| **Green** | Update `wiring.py`: `consume_quotes` and `consume_bars` accept an optional `store: StateStore | None` parameter. When provided and enabled, call `store.save_quote(quote)` / `store.save_bar(bar)` after the state update. Update `app.py` lifespan to create StateStore (from env var `OBSERVER_DB_PATH`, default `None` = disabled). |
| **Refactor** | Ensure persistence errors are logged but don't crash the pipeline (try/except around save calls). |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Phase ordering | Retention first, persistence second | Retention is the M1 gap; persistence is a debugging convenience. Ship the milestone before the nice-to-have. |
| Persistence scope | Quotes + bars only (no candidates) | Candidate persistence with context snapshots belongs in step 130 (Journal). Duplicating it here would create two conflicting persistence paths. |
| Persistence location | `wiring.py` (API layer) | Keeps `MarketState` as a clean synchronous in-memory store. The async boundary in `wiring.py` is the natural hook point. |
| Database | SQLite | Zero configuration, file-based, queryable with standard tools |
| Persistence mode | Optional via `OBSERVER_DB_PATH` env var, off by default | System works without it; enable for debugging/analysis |
| Write-through | Save on every update | Simplest; SQLite handles the throughput for V1 volumes |
| Error handling | Log + continue on persistence failure | Persistence is a debugging aid; it should never crash the hot path |
| Retention enforcement | Per-strategy, configurable via `EngineConfig.max_candidates_per_strategy` | Prevents unbounded candidate growth; each strategy manages its own window |
| No UI changes | — | UI debounce is already handled by 070 wiring design; no frontend work needed |

---

## Acceptance Criteria

- [x] `enforce_retention(max_per_strategy)` removes oldest candidates exceeding the per-strategy limit
- [x] `enforce_retention` returns the removed candidates
- [x] Different strategies have independent retention limits
- [x] `EngineConfig` has `max_candidates_per_strategy` field (default 10)
- [x] `Engine.evaluate()` calls `enforce_retention` after `invalidate_expired`
- [x] `StateStore(db_path=None)` is a no-op (enabled=False, saves are silent, gets return [])
- [x] `StateStore(db_path=":memory:")` creates quotes + bars tables
- [x] Quote save/get round-trip works, with symbol and `since` filtering
- [x] Bar save/get round-trip works, with symbol, timeframe, and `since` filtering
- [x] `wiring.py` calls `StateStore.save_quote`/`save_bar` when persistence is enabled
- [x] Persistence errors are logged but do not crash the pipeline
- [x] `OBSERVER_DB_PATH` environment variable controls persistence (unset = disabled)
- [ ] `sqlite3 $OBSERVER_DB_PATH "SELECT count(*) FROM quotes;"` shows data after running with persistence enabled (manual verification)
- [x] All existing tests continue to pass (278 passed)
- [x] New unit tests pass for retention and persistence

---

## Manual Verification

```bash
# 1. Run all unit tests
cd backend && python -m pytest tests/unit/ -v

# 2. Start backend with persistence enabled
cd backend && OBSERVER_DB_PATH=observer.db PYTHONPATH=src uvicorn api.app:create_app --factory --port 8000

# 3. Let it run for ~2 minutes, then inspect the database
sqlite3 observer.db "SELECT count(*) FROM quotes;"
sqlite3 observer.db "SELECT count(*) FROM bars;"
sqlite3 observer.db "SELECT * FROM bars WHERE symbol='ESH26' ORDER BY timestamp DESC LIMIT 10;"

# 4. Start backend WITHOUT persistence (default) — verify no errors
cd backend && PYTHONPATH=src uvicorn api.app:create_app --factory --port 8000
# Confirm no observer.db file is created and no errors in logs

# 5. Check retention: with max_candidates_per_strategy=10 (default),
#    after enough bar-close evaluations, verify CandidateStore never
#    holds more than 10 candidates per strategy:
curl -s http://localhost:8000/api/snapshot | python -m json.tool
# Inspect the candidates array — count per strategy should be <= 10
```

---

## Data Flow (updated)

```
consume_quotes (wiring.py)
  ├─ state.update_quote(q)
  ├─ store.save_quote(q)         ← new (when persistence enabled)
  └─ ws_manager.broadcast(quote_update)

consume_bars (wiring.py)
  ├─ engine.on_bar(bar)          → state.update_bar + evaluate
  │   └─ evaluate():
  │       ├─ strategy.evaluate(ctx)
  │       ├─ store.add(candidate)
  │       ├─ store.invalidate_expired(now)
  │       └─ store.enforce_retention(max)  ← new
  ├─ store.save_bar(bar)         ← new (when persistence enabled)
  ├─ ws_manager.broadcast(bar_update)
  └─ ws_manager.broadcast(candidates_update)
```

---

## Out of Scope

- **Candidate persistence / journaling** → step 130 (richer design with context snapshots)
- DuckDB (evaluate later if SQLite performance is insufficient)
- Chain snapshots / greeks persistence (v2+)
- Replay from persisted data (future SimProvider enhancement)
- Data retention policies / cleanup
- UI changes (not needed — 070 wiring already limits candidate broadcasts to bar-close)
