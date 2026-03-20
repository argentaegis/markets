---
name: 110 ORB 5m Strategy
overview: "Implement Opening Range Breakout (5-minute) strategy for futures. Entry on breakout above/below first 5m RTH bar, stop at opposite side, targets at 1R/2R. Prerequisite: add specs to Context. Test-first with canned bar data."
todos: []
isProject: false
---

# 110: ORB 5-Minute Strategy

Conforms to [000_observer_mvp_initial_plan.md](000_observer_mvp_initial_plan.md) §strategies/ and M3 milestone.

---

## Project Practice: Test-First (Red-Green-Refactor)

| Stage | Description |
|-------|--------------|
| **Red** | Write failing tests that specify the expected behavior. Run tests; they fail. |
| **Green** | Implement minimal code to make the tests pass. Run tests; they pass. |
| **Refactor** | Clean up implementation while keeping tests green. |

---

## Objective

Implement the first real futures strategy: **Opening Range Breakout on 5-minute bars**. The strategy identifies the opening range (first 5-minute bar of the RTH session), then emits trade candidates when price breaks above or below that range.

**Prerequisite change:** Add `specs: dict[str, ContractSpec]` to `Context` (and `MarketSnapshot`) so all strategies have access to contract metadata (tick size, point value, session hours).

---

## Existing Foundation

- Step 020: canonical types (TradeCandidate, Bar, FutureSymbol, ContractSpec, TradingSession)
- Step 050: BaseStrategy, Requirements, Context
- Step 060: Engine triggers evaluation on bar close
- `core/tick.py`: `normalize_price()`, `ticks_between()` for tick-exact price math

---

## Strategy Logic

### Opening Range Definition

- **Opening range** = High and Low of the first 5-minute bar after RTH session open
- RTH for ES/NQ: 9:30 AM Eastern to 4:00 PM Eastern (timezone-aware, handles DST automatically)
- The first 5m bar close is at 9:35 AM Eastern
- Session detection uses `zoneinfo.ZoneInfo` + `ContractSpec.session` — never hardcoded UTC offsets

### Candidate Generation

On each subsequent 5m bar close during the session:

| Condition | Candidate |
|-----------|-----------|
| Bar close > OR High | LONG candidate |
| Bar close < OR Low | SHORT candidate |
| Bar close within OR | No candidate |

### Entry / Stop / Target

| Field | LONG | SHORT |
|-------|------|-------|
| Direction | LONG | SHORT |
| Entry type | STOP (buy stop above OR high) | STOP (sell stop below OR low) |
| Entry price | OR High + 1 tick | OR Low - 1 tick |
| Stop price | OR Low - 1 tick | OR High + 1 tick |
| Target 1 | Entry + 1R | Entry - 1R |
| Target 2 | Entry + 2R | Entry - 2R |

Where R = distance from entry to stop (the "risk").

All prices are tick-normalized via `core.tick.normalize_price()`.

### Score Heuristic

Score is based on opening range size relative to the allowed range (sweet-spot principle):

```
range_ticks = ticks_between(or_low, or_high, tick_size)
midpoint = (min_range_ticks + max_range_ticks) / 2
deviation = abs(range_ticks - midpoint) / midpoint
score = max(30.0, 80.0 - (deviation * 40.0))
```

Ranges near the midpoint of min/max get ~80; extreme sizes get ~30–40. Step 130 will normalize across strategies.

### Explain Bullets

Each candidate includes 3-6 "why" bullets:

1. "ORB 5m: price broke {above/below} opening range"
2. "Opening range: {OR_low} – {OR_high} ({range_ticks} ticks)"
3. "Risk (1R): {risk_ticks} ticks = ${risk_dollars:.2f}"
4. "Session volume at breakout: {volume}"
5. "Time since open: {minutes} minutes"

### Validity

- `valid_until` = RTH session close for the evaluation date
- Construction: convert `ctx.timestamp` to Eastern via `zoneinfo.ZoneInfo(spec.session.timezone)`, extract the date, build `datetime(date, session.end_time, tzinfo=eastern_tz)`, convert to UTC
- Candidate expires at end of session regardless of fill

### Filters (basic)

- Minimum opening range size: configurable (default 4 ticks for ES)
- Maximum opening range size: configurable (default 40 ticks for ES)
- Only generate once per direction per session (no repeated breakout signals)

### Session State

The ORB strategy maintains instance state across `evaluate()` calls:

- `_or_high: float | None` — opening range high for the current session
- `_or_low: float | None` — opening range low for the current session
- `_session_date: date | None` — current session date (reset clears OR + fired directions)
- `_fired: set[Direction]` — which directions have emitted candidates this session

This state is reset when a new session day is detected. This is acceptable because the Engine owns strategy instances and calls `evaluate()` sequentially — no concurrency concerns.

Note: `CandidateStore.add()` already deduplicates on `(symbol, strategy, direction)` with replace semantics. The strategy's own `_fired` tracking provides a stronger guarantee (prevents emission entirely rather than relying on store-level replacement).

---

## Interface Contract

### Constructor

```python
class ORB5mStrategy(BaseStrategy):
    def __init__(
        self,
        symbols: list[str] | None = None,
        min_range_ticks: int = 4,
        max_range_ticks: int = 40,
    ) -> None:
        """
        symbols: canonical symbols to evaluate (default ["ESH26"])
        min/max_range_ticks: filter thresholds for opening range size
        """
```

Constructor accepts configurable parameters. Step 120 (Strategy Registry) will pass these from `config.yaml` per-strategy params.

### Requirements

```python
def requirements(self) -> Requirements:
    return Requirements(
        symbols=self._symbols,
        timeframes=["5m"],
        lookback=80,       # full RTH session = ~78 5m bars
        needs_quotes=False,
    )
```

### evaluate() contract

```python
def evaluate(self, ctx: Context) -> list[TradeCandidate]:
    # For each configured symbol:
    #   1. Get ContractSpec from ctx.specs[symbol]
    #   2. Determine current session date (Eastern time)
    #   3. If new session: reset OR + fired set
    #   4. Find first RTH bar -> set OR high/low
    #   5. Check latest bar for breakout
    #   6. Apply filters (range size, once-per-direction)
    #   7. Build TradeCandidate with tick-normalized prices
```

---

## Module Layout

```
backend/src/strategies/
  __init__.py
  base.py                    # (existing from 050)
  dummy_strategy.py          # (existing from 050)
  orb_5m.py                  # ORB 5-minute strategy

backend/tests/unit/strategies/
  __init__.py                # (existing)
  conftest.py                # (existing, extended with bar factory helpers)
  test_base.py               # (existing)
  test_dummy_strategy.py     # (existing)
  test_orb_5m.py             # ORB strategy tests with canned data
```

No JSON fixture files — bar sequences are built via Python factory functions in `conftest.py`, consistent with the project's test data pattern.

---

## Implementation Phases

### Phase 0: Add specs to Context (prerequisite)

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests in `test_context.py`: `Context` accepts `specs` kwarg; defaults to `{}`; existing tests still pass without `specs` arg. Write tests in `test_market_state.py`: `MarketState` initialized with specs; `get_context()` includes specs; `get_snapshot()` includes specs |
| **Green** | Add `specs: dict[str, ContractSpec] = field(default_factory=dict)` to `Context` and `MarketSnapshot`. Add `specs` parameter to `MarketState.__init__()`, store as `self._specs`, include in `get_context()` and `get_snapshot()`. Update `Engine.__init__()` or wiring to pass specs. |
| **Refactor** | Verify all existing tests still pass (backward-compatible default). Update `__init__.py` exports if needed. |

### Phase 1: Test helpers + Opening range identification

| Stage | Tasks |
|-------|-------|
| **Red** | Add bar factory helpers to `conftest.py`: `make_bar(symbol, timeframe, timestamp, o, h, l, c, volume)` with sensible defaults. Write `test_orb_5m.py` tests: given bars including the first 5m bar after RTH open, identify OR high and low correctly; handle missing first bar (no OR set, no candidates); handle pre-market bars (ignored); detect new session date resets OR state |
| **Green** | Implement `ORB5mStrategy.__init__()`, `name`, `requirements()`, and OR identification logic. Use `zoneinfo.ZoneInfo(spec.session.timezone)` to convert bar timestamps to local time for RTH detection. |
| **Refactor** | Extract `_is_rth_bar()` and `_get_session_date()` helpers |

### Phase 2: Breakout detection

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: bar closing above OR high triggers LONG candidate; bar closing below OR low triggers SHORT candidate; bar within range produces no candidate; only first breakout per direction per session (second breakout in same direction returns empty) |
| **Green** | Implement breakout detection in `evaluate()` using `_fired` set |
| **Refactor** | Clean up state tracking (which breakouts have fired this session) |

### Phase 3: Entry / Stop / Target calculation

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: entry at OR boundary + 1 tick; stop at opposite boundary ± 1 tick; targets at 1R and 2R; all prices normalized to tick size via `normalize_price()`; risk calculation correct; `ticks_between()` used for R |
| **Green** | Implement price calculations using `ContractSpec.tick_size` and `core.tick` functions |
| **Refactor** | Ensure all price arithmetic uses `normalize_price()` for final output |

### Phase 4: Score, explain bullets, validity, tags

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: score follows sweet-spot heuristic (range at midpoint -> ~80, range at extremes -> ~30-40); explain contains 3-5 bullets with expected content; `valid_until` is RTH session close in UTC; tags include `strategy: "orb_5m"` and `setup: "breakout_long"` or `"breakout_short"` |
| **Green** | Implement score calculation, explain generation, `valid_until` construction (ET -> UTC), tags |
| **Refactor** | Parameterize bullet templates; verify DST-aware `valid_until` |

### Phase 5: Filters

| Stage | Tasks |
|-------|-------|
| **Red** | Write tests: OR range below `min_range_ticks` -> no candidates all session; OR range above `max_range_ticks` -> no candidates all session; filter thresholds configurable via constructor; default values (4, 40) used when not specified |
| **Green** | Implement range size filters applied at OR identification time (reject OR, don't just skip candidates) |
| **Refactor** | Log a message when OR is filtered out (aids debugging) |

### Phase 6: Integration test with engine

| Stage | Tasks |
|-------|-------|
| **Red** | Write integration test: build a sequence of bars spanning a simulated RTH session (pre-market -> OR bar -> breakout bar -> additional bars). Feed through `Engine.on_bar()` with `ORB5mStrategy`. Assert: OR identified after first RTH bar, LONG candidate emitted on breakout, no duplicate candidates, candidate has correct prices/score/explain. |
| **Green** | Ensure all components wire together; fix any integration issues |
| **Refactor** | Add a second integration test: full session with no breakout (close always inside range) -> zero candidates |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Timeframe | 5-minute bars | ORB_5m per locked decision; fast signal, well-defined |
| OR definition | First 5m bar of RTH only | Simple, unambiguous; multi-bar OR is v2 |
| Entry type | Stop order (breakout entry) | Natural for range breakout; triggers on price crossing level |
| Risk unit (R) | Entry to stop distance | Standard R-multiple framework |
| Strategy instance state | Mutable `_or_high`, `_or_low`, `_session_date`, `_fired` | ORB inherently needs session state; engine owns strategy instances, calls evaluate() sequentially — no concurrency risk |
| Timezone handling | `zoneinfo.ZoneInfo` from `ContractSpec.session.timezone` | Correct across DST boundaries; never hardcode UTC offsets |
| `valid_until` construction | Convert ctx.timestamp to ET, build session close datetime, convert to UTC | Robust across DST; uses ContractSpec.session.end_time |
| Score heuristic | Sweet-spot based on range size relative to min/max | Simple, meaningful; step 130 normalizes across strategies |
| Filter defaults | ES: min 4 ticks, max 40 ticks | Avoid trivially small or unusually large ranges |
| Symbols | Configurable via constructor (default `["ESH26"]`) | Ready for step 120 strategy registry with per-strategy params |
| Test data | Python factory functions in conftest.py | Consistent with project pattern; no JSON fixture I/O overhead |
| Specs in Context | `specs: dict[str, ContractSpec]` added to Context with default `{}` | Every real strategy needs contract metadata; backward-compatible default |

---

## Acceptance Criteria

- [ ] `Context` and `MarketSnapshot` include `specs: dict[str, ContractSpec]` (default `{}`)
- [ ] `MarketState` accepts and propagates specs to context/snapshot
- [ ] All existing tests pass without modification (backward-compatible default)
- [ ] `ORB5mStrategy` implements `BaseStrategy`
- [ ] Constructor accepts `symbols`, `min_range_ticks`, `max_range_ticks`
- [ ] `requirements()` returns lookback=80, timeframes=["5m"], needs_quotes=False
- [ ] Correctly identifies opening range from first 5m RTH bar using timezone-aware detection
- [ ] Emits LONG candidate on breakout above OR
- [ ] Emits SHORT candidate on breakout below OR
- [ ] Entry, stop, target prices calculated correctly and tick-normalized
- [ ] Score follows sweet-spot heuristic (range midpoint -> ~80, extremes -> ~30-40)
- [ ] Explain bullets include range size, risk in ticks and dollars, and session context
- [ ] `valid_until` set to RTH session close (timezone-aware, DST-correct)
- [ ] No duplicate candidates per direction per session
- [ ] Range size filters prevent signals on extreme ranges
- [ ] New session day resets OR state and fired directions
- [ ] Integration test: bars through Engine -> expected ORB candidates
- [ ] All tests pass: `pytest backend/tests/unit/strategies/ backend/tests/unit/state/`

---

## Manual Verification

### With SimProvider (available now)

1. Start backend with SimProvider and ORB strategy enabled:
   ```bash
   cd /Users/ajones/Code/observer/backend
   PYTHONPATH=src uvicorn api.app:create_app --factory --port 8000
   ```
2. Open frontend at `http://localhost:5173`
3. Observe SimProvider bars arriving (check browser console or backend logs)
4. Note: SimProvider generates bars at regular intervals but timestamps may not align with real RTH hours. To verify ORB logic, check backend logs for OR identification and breakout detection messages.
5. For a controlled test, temporarily adjust the session times or use a test script that feeds bars directly to the engine.

### With Schwab provider (when available, during market hours)

1. Start backend with Schwab provider:
   ```bash
   cd /Users/ajones/Code/observer/backend
   OBSERVER_PROVIDER=schwab PYTHONPATH=src uvicorn api.app:create_app --factory --port 8000
   ```
2. Wait for RTH session open (9:30 AM ET)
3. After first 5m bar (9:35 AM ET), verify opening range identified (check logs)
4. When/if breakout occurs, verify candidate appears in UI with correct entry/stop/target
5. Verify candidate expires at 4:00 PM ET

---

## Data Flow

```
Provider (5m bars)
  -> Engine.on_bar()
    -> MarketState.update_bar()
    -> Engine.evaluate()
      -> MarketState.get_context() [includes specs]
      -> ORB5mStrategy.evaluate(ctx)
        -> Read bars from ctx.bars[symbol]["5m"]
        -> Read spec from ctx.specs[symbol]
        -> Identify OR / detect breakout / calculate prices
        -> Return list[TradeCandidate]
      -> CandidateStore.add()
    -> WebSocket broadcast
```

---

## Out of Scope

- Multi-bar opening range (e.g., 15m or 30m OR)
- ORB with volume confirmation
- Fade (counter-trend) ORB setups
- Backtesting this strategy against historical data (separate tool)
- Auto-execution of ORB signals
- Dynamic tick-size lookup (uses ContractSpec from provider)
