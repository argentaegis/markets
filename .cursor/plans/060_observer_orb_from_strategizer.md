---
name: 060 Observer ORB From Strategizer
overview: "Wire observer engine to run ORB from strategizer via adapter. Replace or coexist with local ORB. Verify no regression in candidate output."
todos: []
isProject: false
---

# 060: Observer ORB From Strategizer

Conforms to [000_strategizer_mvp_plan.md](000_strategizer_mvp_plan.md) §4.3.

---

## Objective

Wire the observer engine to run ORB from the strategizer package instead of (or alongside) the local ORB strategy. Use the adapter from step 050. Verify that TradeCandidates match or improve on current ORB behavior.

---

## Existing Foundation

- Step 050: Adapter (context_to_strategizer_input, signal_to_trade_candidate, ObserverPortfolioView)
- Step 040: Engine passes portfolio to strategies
- observer: StrategyRegistry, config.yaml, Engine
- Local ORB: observer/backend/src/strategies/orb_5m.py

---

## Integration Options

### Option A: Replace local ORB

- Remove or deprecate local ORB5mStrategy
- StrategyRegistry loads ORB from strategizer when config says source: strategizer
- Config: `strategies.orb_5m.source: strategizer`

### Option B: Coexist

- Keep local ORB
- Add StrategizerORBAdapter that wraps strategizer ORB + adapter
- Config chooses which to use per strategy

**Recommendation:** Option A for MVP — single ORB implementation in strategizer. Local ORB can remain for reference or be removed.

---

## Wiring

### StrategyRegistry / Config

- Config: `strategies.orb_5m.source: strategizer` (or `strategies.orb_5m: { source: strategizer, params: {...} }`)
- Registry: When source=strategizer, instantiate strategizer.ORB5mStrategy, wrap in adapter
- Adapter wrapper: Implements BaseStrategy (observer interface), delegates to strategizer strategy

### Adapter Strategy Wrapper

`StrategizerStrategyAdapter` implements `BaseStrategy`. Engine calls `strategy.evaluate(ctx)` for all strategies — no Engine changes. The adapter encapsulates conversion.

```python
class StrategizerStrategyAdapter(BaseStrategy):
    """Wraps a strategizer Strategy for observer engine."""
    def __init__(self, strategy: strategizer.Strategy) -> None:
        self._strategy = strategy

    @property
    def name(self) -> str:
        return self._strategy.name

    def requirements(self) -> Requirements:
        r = self._strategy.requirements()
        return Requirements(symbols=r.symbols, timeframes=r.timeframes,
                            lookback=r.lookback, needs_quotes=r.needs_quotes)

    def evaluate(self, ctx: Context) -> list[TradeCandidate]:
        ts, bars_by_symbol, specs, portfolio_view = context_to_strategizer_input(ctx)
        signals = self._strategy.evaluate(ts, bars_by_symbol, specs, portfolio_view)
        return [signal_to_trade_candidate(s, self._strategy.name, ctx.timestamp) for s in signals]
```

Portfolio comes from `ctx.portfolio` (050: `context_to_strategizer_input(ctx)` takes ctx only).

---

## Engine Flow

**No Engine changes.** Engine continues to call `strategy.evaluate(ctx)` for every strategy. The adapter implements that interface and handles conversion internally.

```
Engine.evaluate(ts)
  -> ctx = state.get_context(timestamp=ts, portfolio=portfolio)
  -> for strategy in strategies:
       candidates = strategy.evaluate(ctx)   # adapter or legacy, same interface
  -> store.add(candidates)
```

---

## Implementation Phases

### Phase 0: StrategizerStrategyAdapter

| Stage | Tasks |
|-------|-------|
| Implement | StrategizerStrategyAdapter wrapping any strategizer Strategy |
| Map | requirements() from strategizer strategy.requirements() |
| Map | evaluate(ctx) -> adapt ctx, call strategy, adapt output |

### Phase 1: Registry integration

| Stage | Tasks |
|-------|-------|
| Extend | StrategyEntry: add `source: str | None = None` |
| Extend | config.py: parse `strategies.<name>.source` from YAML |
| Extend | StrategyRegistry.instantiate: when `entry.source == "strategizer"`, use strategy map instead of discovery |
| Map | MVP: `{"orb_5m": strategizer.strategies.orb_5m.ORB5mStrategy}` |
| Config | strategies.orb_5m: source: strategizer, watchlist, params |

### Phase 2: Tests

| Stage | Tasks |
|-------|-------|
| Integration | Feed bars through engine with strategizer ORB; assert candidates |
| Regression | Compare output to local ORB (if kept) on same input |
| Unit | StrategizerStrategyAdapter tests |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Wrapper pattern | StrategizerStrategyAdapter | Observer engine expects BaseStrategy; adapter implements it |
| Engine changes | None | Adapter implements evaluate(ctx); Engine stays uniform |
| requirements() | Delegate to inner strategy | Map strategizer Requirements to observer Requirements |
| Config key | source: strategizer | Explicit; backward compat when absent |

---

## Files to Touch

| File | Change |
|------|--------|
| config.py | Add `source` to StrategyEntry; parse from YAML |
| strategies/strategizer_adapter.py | Add StrategizerStrategyAdapter class |
| strategies/registry.py | Branch on entry.source; strategy map for source=strategizer |
| config.example.yaml | Add `source: strategizer` under orb_5m |

---

## Acceptance Criteria

- [ ] Config enables orb_5m from strategizer
- [ ] Engine runs ORB and produces TradeCandidates
- [ ] Candidates have correct entry/stop/targets, score, explain
- [ ] No regression vs local ORB (or local ORB removed)
- [ ] Integration test: bars -> engine -> candidates

---

## Out of Scope

- Additional strategizer strategies
- Strategy discovery (manual config)

---

## Implementation Order

1. Implement StrategizerStrategyAdapter + unit tests
2. Add source to StrategyEntry and config parsing
3. Extend Registry: strategy map, branch on source=strategizer
4. Update config.example.yaml
5. Integration test: engine + strategizer ORB -> candidates
6. (Option A) Remove or deprecate local ORB
