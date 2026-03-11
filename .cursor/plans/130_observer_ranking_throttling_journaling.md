---
name: 130 Ranking Throttling Journaling
overview: "Implement pass-through score normalization, top-N candidate filtering, per-strategy throttle limits, and SQLite journaling of all recommendations + input features. Consolidate ranking/filtering into Engine pipeline. Test-first."
todos: []
isProject: false
---

# 130: Ranking, Throttling, and Journaling

Conforms to [000_observer_mvp_initial_plan.md](000_observer_mvp_initial_plan.md) §engine/ ranking and M5 milestone.

---

## Project Practice: Test-First (Red-Green-Refactor)

| Stage | Description |
|-------|--------------|
| **Red** | Write failing tests that specify the expected behavior. Run tests; they fail. |
| **Green** | Implement minimal code to make the tests pass. Run tests; they pass. |
| **Refactor** | Clean up implementation while keeping tests green. |

---

## Objective

Prevent alert flood and enable post-session analysis:
1. **Score normalization** — add `normalized_score` field to `TradeCandidate`; pass-through (`normalized_score = score`) for V1 since all strategies already produce 0-100 scores; normalization hook preserved for future cross-strategy scaling
2. **Top-N filtering** — only surface the best candidates to the UI (configurable global limit)
3. **Per-strategy throttling** — consolidated into existing `CandidateStore.enforce_retention` (best scores win instead of newest)
4. **Journaling** — persist all candidates (pre-filter) and their market context to SQLite for post-session "why did this fire?" inspection

---

## Existing Foundation

- Step 060: Engine + CandidateStore (with `enforce_retention(max_per_strategy)`)
- Step 090: SQLite persistence (StateStore with quotes/bars tables)
- Step 120: config.yaml with per-strategy params, `EngineConfig`

---

## Key Design Decisions (from evaluation)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Normalization | Pass-through (`normalized_score = score`) | With 2 strategies both producing 0-100 scores, min-max normalization is misleading — a single candidate always gets 100, two close scores (60 vs 65) get stretched to 0 vs 100. Identity transform preserves real scores. |
| Ranker/Throttle classes | No separate classes — consolidate into Engine pipeline | `CandidateStore.enforce_retention` already does per-strategy limiting. Adding `Ranker` + `Throttle` classes creates overlap. A single `_rank_and_filter()` method in Engine is simpler. |
| `normalized_score` on TradeCandidate | New optional field (`float | None = None`) | `TradeCandidate` is frozen; can't mutate after creation. Adding a defaulted field preserves backward compatibility. |
| Context snapshot | `{"bars": {sym: {tf: [last 10 bars]}}, "quotes": {sym: quote}}` | Concrete, bounded. Enough to answer "what did the market look like?" No "indicators" — strategies don't expose them yet. |
| Journal DB | Same SQLite file as StateStore | One DB file to manage. Journal table doesn't conflict with quotes/bars. Split if access patterns diverge in V2. |
| Config surface | Minimal: `top_n` + `journal_enabled` on EngineConfig | Per-strategy throttle overrides, normalization strategy selection, and context_bars are premature config for V1. Hardcode sensible defaults. |
| Journal on restart | Append-only; existing records survive restart | Journal DB is not cleared on startup — historical data accumulates across sessions. |

---

## Interface Contract

### TradeCandidate change

```python
@dataclass(frozen=True)
class TradeCandidate:
    # ... existing fields unchanged ...
    score: float
    normalized_score: float | None = None   # NEW — defaults to None
    # ... rest unchanged ...
```

Strategies may set `normalized_score` explicitly. If `None`, the Engine pipeline sets it equal to `score` (pass-through).

### Engine pipeline change

```python
class Engine:
    def evaluate(self, timestamp=None) -> list[TradeCandidate]:
        """Run strategies -> normalize -> throttle -> top_n -> journal."""
        # 1. Collect raw candidates from all strategies
        # 2. Journal ALL raw candidates (pre-filter) with context snapshot
        # 3. Assign normalized_score = score where None
        # 4. Add to CandidateStore (dedup + enforce_retention by score)
        # 5. Return top_n from active candidates
```

### Journal (added to StateStore)

```python
class StateStore:
    # ... existing quote/bar methods ...

    def save_journal_entry(self, entry: JournalEntry) -> None:
        """Persist a candidate + context snapshot."""

    def get_journal_entries(
        self,
        since: datetime | None = None,
        strategy: str | None = None,
        symbol: str | None = None,
    ) -> list[JournalEntry]:
        """Query journal with optional filters."""
```

### JournalEntry

```python
@dataclass(frozen=True)
class JournalEntry:
    """Candidate + market context at time of creation."""
    candidate_id: str
    timestamp: datetime
    symbol: str
    strategy: str
    direction: str
    entry_type: str
    entry_price: float
    stop_price: float
    targets: list[float]       # stored as JSON
    score: float
    normalized_score: float
    explain: list[str]         # stored as JSON
    valid_until: datetime
    tags: dict[str, str]       # stored as JSON
    context_snapshot: dict     # stored as JSON — bars + quotes
```

### EngineConfig extension

```python
@dataclass(frozen=True)
class EngineConfig:
    eval_timeframe: str = "5m"
    max_candidates_per_strategy: int = 10
    top_n: int = 5
    journal_enabled: bool = True
```

### config.yaml extension

```yaml
engine:
  eval_timeframe: "5m"
  max_candidates_per_strategy: 10
  top_n: 5
  journal_enabled: true
```

No `normalization:`, no per-strategy `throttle:` overrides, no `context_bars:` — these can be added when there's a real need.

### Context snapshot format

```python
def _build_context_snapshot(ctx: Context, symbols: list[str]) -> dict:
    """Extract bounded market context for journaling."""
    MAX_BARS = 10
    snapshot: dict = {"bars": {}, "quotes": {}}
    for sym in symbols:
        if sym in ctx.quotes:
            q = ctx.quotes[sym]
            snapshot["quotes"][sym] = {
                "bid": q.bid, "ask": q.ask, "last": q.last,
                "volume": q.volume, "timestamp": q.timestamp.isoformat(),
            }
        sym_bars = ctx.bars.get(sym, {})
        if sym_bars:
            snapshot["bars"][sym] = {}
            for tf, bars in sym_bars.items():
                snapshot["bars"][sym][tf] = [
                    {
                        "open": b.open, "high": b.high, "low": b.low,
                        "close": b.close, "volume": b.volume,
                        "timestamp": b.timestamp.isoformat(),
                    }
                    for b in bars[-MAX_BARS:]
                ]
    return snapshot
```

---

## Module Layout

```
backend/src/core/
  candidate.py             # (existing, add normalized_score field)

backend/src/engine/
  __init__.py              # (existing)
  engine.py                # (existing, add _rank_and_filter + _ensure_normalized + journal wiring)
  candidate_store.py       # (existing, update enforce_retention to sort by score not age)
  config.py                # (existing, add top_n + journal_enabled)
  journal.py               # JournalEntry dataclass + _build_context_snapshot helper

backend/src/state/
  persistence.py           # (existing, add journal table + save/query methods)

backend/tests/unit/engine/
  test_engine.py           # (existing, add ranking/filtering/journal tests)
  test_candidate_store.py  # (existing, update enforce_retention tests for score-based)
  test_journal.py          # NEW — journal persistence round-trip

backend/tests/unit/
  test_config.py           # (existing, add top_n + journal_enabled tests)
```

---

## Implementation Phases

### Phase 1: Add `normalized_score` to TradeCandidate + update enforce_retention

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: `TradeCandidate` accepts optional `normalized_score` (defaults `None`); existing tests still pass with no `normalized_score` arg; `CandidateStore.enforce_retention` keeps candidates with highest `score` (not newest `created_at`) when exceeding limit |
| **Green** | Add `normalized_score: float | None = None` to `TradeCandidate` (after `score`, before `explain` — order matters for frozen dataclass). Update `enforce_retention` sort key from `created_at` to `score` (descending). |
| **Refactor** | Verify all existing strategy tests pass unchanged (field has a default so backward-compatible). Update any test that relied on age-based retention ordering. |

### Phase 2: Engine ranking/filtering pipeline

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: `Engine.evaluate()` sets `normalized_score = score` on candidates where it's `None`; `evaluate()` returns at most `top_n` candidates sorted by score descending; with `top_n=2` and 5 candidates, only best 2 are returned to caller; per-strategy limit still enforced via `enforce_retention` |
| **Green** | Add `_ensure_normalized()` (fills `None` -> `score` via `dataclasses.replace`). Add `_rank_and_filter()` that sorts active candidates by `normalized_score` desc and slices to `top_n`. Update `evaluate()` to call these after strategy evaluation. Extend `EngineConfig` with `top_n: int = 5`. |
| **Refactor** | Stable sort (ties broken by `created_at` ascending — oldest first, i.e. most established). Ensure `get_active_candidates()` also returns sorted. |

### Phase 3: Journal persistence

| Stage | Tasks |
|-------|-------|
| **Red** | Write `test_journal.py`: `JournalEntry` round-trip through `StateStore.save_journal_entry` / `get_journal_entries`; query by `since`, `strategy`, `symbol` filters; `context_snapshot` stored and retrieved as dict; `targets`, `explain`, `tags` survive JSON serialization; journal table created when `StateStore` is enabled |
| **Green** | Add `JournalEntry` dataclass in `engine/journal.py`. Add `_build_context_snapshot()` helper. Add journal table schema to `StateStore._SCHEMA`. Implement `save_journal_entry()` and `get_journal_entries()` on `StateStore`. Add `journal_enabled: bool = True` to `EngineConfig`. |
| **Refactor** | Add index on `(strategy, timestamp)` for efficient queries. Ensure `JournalEntry` fields match the schema table. |

### Phase 4: Wire journal into Engine + config + manual verification

| Stage | Tasks |
|-------|-------|
| **Red** | Write integration test: Engine with `journal_enabled=True` records ALL raw candidates (pre-filter) to journal; journal entries include `context_snapshot` with bars and quotes; UI (via `get_active_candidates`) receives only `top_n` filtered candidates; `journal_enabled=False` skips recording |
| **Green** | Update `Engine.__init__` to accept optional `StateStore` for journaling. In `evaluate()`, after collecting raw candidates and before filtering, call `_build_context_snapshot` and `store.save_journal_entry()` for each candidate. Update `app.py` to pass `store` to `Engine`. Update `load_config` to parse `top_n` and `journal_enabled`. Update `config.example.yaml`. |
| **Refactor** | Manual verification: start backend with `config.yaml`, generate candidates, query `journal.db` with `sqlite3` to see stored records with context snapshots. Verify UI shows only `top_n` candidates. |

---

## Journal Table Schema

```sql
CREATE TABLE IF NOT EXISTS journal (
    candidate_id     TEXT    NOT NULL,
    timestamp        TEXT    NOT NULL,
    symbol           TEXT    NOT NULL,
    strategy         TEXT    NOT NULL,
    direction        TEXT    NOT NULL,
    entry_type       TEXT    NOT NULL,
    entry_price      REAL    NOT NULL,
    stop_price       REAL    NOT NULL,
    targets          TEXT    NOT NULL,   -- JSON array
    score            REAL    NOT NULL,
    normalized_score REAL    NOT NULL,
    explain          TEXT    NOT NULL,   -- JSON array
    valid_until      TEXT    NOT NULL,
    tags             TEXT    NOT NULL,   -- JSON object
    context_snapshot TEXT    NOT NULL    -- JSON object
);

CREATE INDEX IF NOT EXISTS idx_journal_strategy_ts ON journal (strategy, timestamp);
CREATE INDEX IF NOT EXISTS idx_journal_symbol_ts ON journal (symbol, timestamp);
```

---

## Data Flow

```
Engine.evaluate():
  1. ctx = state.get_context(timestamp)
  2. for each strategy:
       raw_candidates = strategy.evaluate(ctx)
       for each candidate:
         - ensure normalized_score (fill None -> score)
         - if journal_enabled: build context snapshot, save_journal_entry()
       - add to CandidateStore (dedup + enforce_retention by score)

  3. active = store.get_active(now)
  4. sorted by normalized_score desc (ties: oldest created_at first)
  5. return active[:top_n]

UI receives: top_n best active candidates
Journal contains: ALL candidates ever generated (pre-filter), append-only
```

---

## Acceptance Criteria

- [ ] `TradeCandidate` has optional `normalized_score` field (defaults `None`)
- [ ] All existing strategy/engine tests pass unchanged
- [ ] `CandidateStore.enforce_retention` keeps highest-score candidates (not newest)
- [ ] `Engine.evaluate()` fills `normalized_score = score` where `None`
- [ ] `Engine.evaluate()` returns at most `top_n` candidates sorted by score
- [ ] `EngineConfig` has `top_n: int = 5` and `journal_enabled: bool = True`
- [ ] `config.yaml` / `load_config()` supports `top_n` and `journal_enabled`
- [ ] `JournalEntry` dataclass captures candidate + context snapshot
- [ ] `StateStore` has journal table with `save_journal_entry` / `get_journal_entries`
- [ ] Journal records ALL candidates (including those filtered out by top_n)
- [ ] `context_snapshot` contains last 10 bars + latest quote per symbol
- [ ] Journal entries survive restart (append-only, not cleared)
- [ ] `sqlite3 observer.db "SELECT * FROM journal LIMIT 5;"` shows stored records
- [ ] UI shows only top-N filtered candidates (no alert flood)
- [ ] `journal_enabled: false` in config skips journal recording

---

## Manual Verification

1. Create `config.yaml` with both strategies enabled and `top_n: 3`:
   ```yaml
   watchlists:
     futures_main:
       - ESH26

   strategies:
     orb_5m:
       enabled: true
       watchlist: futures_main
       params:
         min_range_ticks: 4
         max_range_ticks: 40
     dummy:
       enabled: true

   engine:
     eval_timeframe: "5m"
     max_candidates_per_strategy: 10
     top_n: 3
     journal_enabled: true
   ```
2. Start backend with persistence:
   ```bash
   cd /Users/ajones/Code/observer/backend
   OBSERVER_DB_PATH=observer.db PYTHONPATH=src uvicorn api.app:create_app --factory --port 8000
   ```
3. Wait for candidates to appear in UI — should see at most 3
4. Query journal:
   ```bash
   sqlite3 observer.db "SELECT strategy, count(*) FROM journal GROUP BY strategy;"
   sqlite3 observer.db "SELECT candidate_id, symbol, strategy, score, normalized_score FROM journal ORDER BY timestamp DESC LIMIT 10;"
   sqlite3 observer.db "SELECT context_snapshot FROM journal LIMIT 1;" | python3 -m json.tool
   ```
5. Verify journal has more records than UI shows (pre-filter candidates logged)
6. Set `journal_enabled: false`, restart, verify no new journal entries

---

## Out of Scope

- Cross-strategy min-max/percentile normalization (V2 — when more strategies exist)
- Per-strategy throttle overrides in config (V2 — use `max_candidates_per_strategy` uniformly)
- Configurable context snapshot size (hardcoded to 10 bars)
- Machine learning scoring models
- Cross-strategy portfolio optimization
- Journal export to CSV/JSON (can query SQLite directly)
- Journal retention policies / cleanup
- Real-time journal analytics dashboard
