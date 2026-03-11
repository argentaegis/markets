# 040: Observer Portfolio State — Deep Evaluation

**Plan:** [040_observer_portfolio_state.md](040_observer_portfolio_state.md)  
**Evaluated:** 2026-02-27

---

## Executive Summary

**Verdict: Plan is sound and ready for implementation.** The design is well-scoped, backward compatible, and correctly positioned for 050. A few clarifications and one minor contradiction are documented below.

---

## 1. Scope Alignment

### 1.1 Upstream (000, 001)

- **000 §4.1, §13:** Observer portfolio awareness; mock for MVP. ✓ Aligned.
- **001 roadmap:** 040 precedes 050 (observer adapter) and 060 (observer ORB). ✓ Correct dependency.

### 1.2 Downstream (050)

050 explicitly expects:

> "Step 040: Observer has PortfolioState, Context includes portfolio"

| 050 Expectation | 040 Deliverable |
|-----------------|-----------------|
| `PortfolioState` with `cash`, `positions` | Phase 0: Position, PortfolioState |
| `Position`: instrument_id, qty, avg_price | Phase 0: matching shape |
| Context includes portfolio | Phase 2: Context.portfolio |
| Adapter implements PortfolioView from PortfolioState | 040 doesn't implement PortfolioView (correct; 050 does) |

050's PortfolioView needs `get_equity()`. Mock portfolio has cash=0, positions={}, so equity is 0. The 050 adapter can compute `get_equity()` as `portfolio.cash + sum(...)` or, for mock, return 0. No gap.

---

## 2. Domain Shape: Observer vs Backtester

| Field | Backtester Position | Backtester PortfolioState | 040 Observer Position | 040 Observer PortfolioState |
|-------|---------------------|---------------------------|------------------------|----------------------------|
| instrument_id | ✓ | — | ✓ | — |
| qty | ✓ | — | ✓ | — |
| avg_price | ✓ | — | ✓ | — |
| multiplier | ✓ | — | *deferred* | — |
| instrument_type | ✓ | — | *deferred* | — |
| cash | — | ✓ | — | ✓ |
| positions | — | ✓ | — | ✓ |
| realized_pnl | — | ✓ | *deferred* | — |
| unrealized_pnl | — | ✓ | *deferred* | — |
| equity | — | ✓ | *deferred* | — |

040's minimal design matches strategizer `PositionView` (instrument_id, qty, avg_price) and is sufficient for 050. Future extension points are documented. ✓

---

## 3. Integration Points — Trace

### 3.1 Current Flow

```
Engine.evaluate(ts)
  → ctx = self._state.get_context(timestamp=ts)
  → for strategy in self._strategies: strategy.evaluate(ctx)
```

**Single call site:** `engine.py:49` — `ctx = self._state.get_context(timestamp=ts)`  
**MarketState.get_context:** `market_state.py:72` — returns `Context(timestamp, quotes, bars, specs)`

### 3.2 Target Flow (per plan)

```
Engine.evaluate(ts)
  → portfolio = self._portfolio  # from init or mock
  → ctx = self._state.get_context(timestamp=ts, portfolio=portfolio)
  → for strategy in self._strategies: strategy.evaluate(ctx)
```

Strategies read `ctx.portfolio`; no signature change to `evaluate(ctx)`.

### 3.3 Backward Compatibility

| Caller | Current | With portfolio |
|--------|---------|----------------|
| Engine | `get_context(timestamp=ts)` | `get_context(timestamp=ts, portfolio=self._portfolio)` |
| Tests (direct Context) | `Context(ts, quotes, bars)` | `Context(..., portfolio=default)` |
| Tests (get_context) | `ms.get_context(ts)` | `ms.get_context(ts, portfolio=default)` |

**Recommendation:** Use `field(default_factory=create_mock_portfolio)` on Context so all existing `Context(...)` and `get_context()` calls work without changes. Engine injects real portfolio; tests get mock implicitly.

---

## 4. Plan Clarifications

### 4.1 Phase 2 Contradiction

**Plan says:** "Extend BaseStrategy.evaluate(ctx) -> evaluate(ctx, portfolio) with default"

**Design Decisions say:** "Portfolio in Context vs separate arg | **In Context**"

**Resolution:** Follow the design decision. Keep `evaluate(ctx)`; add `portfolio` to Context. No second argument. Phase 2 task should read: "Context includes portfolio; strategies read ctx.portfolio." Remove the "extend BaseStrategy.evaluate" line.

### 4.2 Engine Ownership of Portfolio

Plan says "Engine receives portfolio (or portfolio factory) at init." Options:

- **A)** Engine receives `PortfolioState` at init; caller passes mock or real.
- **B)** Engine receives a factory `() -> PortfolioState`; calls it each evaluate.

For MVP mock, both work. **Recommendation: A** — pass `PortfolioState` at init. Simpler; Engine keeps `self._portfolio`. App bootstrap creates mock and passes it. Config can control *which* portfolio source is used (mock vs future real), but Engine API stays `Engine(..., portfolio=create_mock_portfolio())`.

### 4.3 Config Phase (Phase 3)

Plan: "config.yaml portfolio section (enabled, source: mock)"

**Current config:** `config.py` loads `engine`, `watchlists`, `strategies`. No `portfolio` section.

**Options:**

1. Add `portfolio: { source: mock }` to config; load into AppConfig; pass to Engine at bootstrap.
2. Defer config: always use mock; add config when a real source exists.

**Recommendation:** Add a minimal `portfolio` section for documentation/future use, even if Engine ignores it for now. Example: `portfolio: { source: mock }`. Engine can default to mock when no portfolio is passed.

---

## 5. Files to Touch

| File | Change |
|------|--------|
| `observer/backend/src/core/portfolio.py` (new) | Position, PortfolioState, create_mock_portfolio |
| `observer/backend/src/state/context.py` | Add `portfolio: PortfolioState` with default_factory |
| `observer/backend/src/state/market_state.py` | `get_context(..., portfolio=None)` — pass through to Context |
| `observer/backend/src/engine/engine.py` | Accept `portfolio` at init; pass to get_context |
| `observer/backend/config.example.yaml` | Add `portfolio: { source: mock }` |
| `observer/backend/src/config.py` | Parse portfolio section (optional; can be no-op for MVP) |
| Tests | Ensure Context and get_context defaults work; Engine tests pass portfolio |

### Test-Only Context Creation (no code change if default works)

- `test_context.py` — 6 uses of `Context(...)`
- `test_market_state.py` — ~10 uses of `ms.get_context(...)`
- `test_dummy_strategy.py` — 3 uses of `Context(...)`
- `test_orb_5m.py` — 2 uses of `Context(...)`
- `strategies/conftest.py` — `ctx_with_bars`, `ctx_empty` fixtures

All should work if `portfolio` has `default_factory=create_mock_portfolio`.

### Engine Integration Points

- `api/app.py` or bootstrap: constructs Engine with `portfolio=create_mock_portfolio()` when loading from config
- `test_engine.py`: `_build_engine()` should pass portfolio (mock is fine)

---

## 6. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Frozen Context: adding field may break existing code | Use default_factory; no existing callers need to change |
| Engine init signature change | Add `portfolio: PortfolioState \| None = None`; use create_mock_portfolio() when None |
| App bootstrap doesn't pass portfolio | Engine uses mock when portfolio is None |

---

## 7. Out-of-Scope Check

- Real persistence, broker integration, PortfolioView impl in observer ✓ Correctly excluded
- 050 will implement PortfolioView adapter ✓

---

## 8. Recommendation

**Proceed with implementation.** Suggested order:

1. **Phase 0:** Create `core/portfolio.py` (Position, PortfolioState, create_mock_portfolio), unit tests.
2. **Phase 2:** Add `portfolio` to Context (default_factory), extend MarketState.get_context, Engine init + evaluate wiring.
3. **Phase 3:** Add portfolio section to config.example.yaml; optionally parse in config.py.
4. **Validation:** Run full observer test suite; ensure no regressions.

Fix the Phase 2 contradiction (portfolio in Context, not second arg) in the plan before implementation.
