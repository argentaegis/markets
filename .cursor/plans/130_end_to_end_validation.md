---
name: 130 End-to-End Validation
overview: "Run ORB in observer (live/mock) and same ORB in backtester on same scenario. Compare outputs. Validates strategizer serves both tools correctly."
todos: []
isProject: false
---

# 130: End-to-End Validation

Conforms to [000_strategizer_mvp_plan.md](000_strategizer_mvp_plan.md) §7 and §9.

---

## Objective

Validate that the same ORB strategy logic executes correctly in both observer and backtester. Run equivalent scenarios through each tool and compare outputs. Confirms the strategizer initiative delivers on its goal: write once, run in both.

---

## Existing Foundation

- Step 060: Observer runs ORB from strategizer
- Step 120: Backtester golden test passes
- Same strategizer ORB code in both

---

## Validation Approach

### Option A: Shared Scenario Data

1. Create a canonical bar sequence (e.g., from golden test fixture)
2. Feed to observer engine (SimProvider or direct bar injection)
3. Run same bars through backtester
4. Compare: observer produces TradeCandidates with entry/stop/target; backtester produces Orders with same prices. Assert consistency.

### Option B: Manual Comparison

1. Run observer with SimProvider, note ORB candidate when breakout occurs
2. Run backtester with same underlying scenario (same bars, same session)
3. Manually verify: entry/stop/target match; backtester Order corresponds to observer TradeCandidate

### Option C: Automated Cross-Tool Test

1. Load golden bar sequence
2. Run observer engine with bar injection; collect TradeCandidates
3. Run backtester with same bars; collect Orders/Fills
4. Assert: for each observer candidate, backtester has matching Order (same symbol, direction, entry_price, stop_price, targets)

**Recommendation:** Option C for full automation; Option A minimal if cross-tool test is complex (different process boundaries, etc.).

---

## Comparison Criteria

| Observer (TradeCandidate) | Backtester (Order/Fill) | Match? |
|---------------------------|-------------------------|--------|
| symbol | instrument_id | Same |
| direction | side (LONG->BUY, SHORT->SELL) | Same |
| entry_price | limit_price or fill_price | Same (tick-aligned) |
| stop_price | (in strategy logic; exit order later) | — |
| targets | (in strategy logic; exit orders later) | — |

For MVP: compare entry intent (symbol, direction, entry_price). Stop and targets are strategy-internal; backtester may generate exit orders in future steps.

---

## Golden Bar Sequence (from 120)

Canonical bars reused from backtester golden fixture:

| Bar | ts (UTC) | open | high | low | close | Role |
|-----|----------|------|------|-----|-------|------|
| 1 | 2026-01-02 14:35 | 5400 | 5410 | 5405 | 5408 | OR bar (9:35 ET) |
| 2 | 2026-01-02 15:00 | 5409 | 5415 | 5408 | 5412 | LONG breakout |

Expected: entry_price 5410.25 (OR high + 1 tick), symbol ESH26, direction LONG.

**Observer Bar format:** `Bar(symbol, timeframe, open, high, low, close, volume, timestamp, source, quality)`. Same OHLC and timestamp; add `volume`, `source="sim"`, `quality=DataQuality.OK`.

---

## Test Location

**Recommendation:** `backtester/tests/integration/test_e2e_orb_consistency.py`. Backtester owns golden fixture. Add observer as optional dev dependency: `observer-backend @ file:../observer/backend`.

---

## Implementation Phases

### Phase 0: Shared fixture

| Stage | Tasks |
|-------|-------|
| Define | `golden_orb_bars()` returning observer Bar instances from canonical sequence |
| Reuse | Same OHLC/ts as backtester ESH26_5m golden (120) |

### Phase 1: Observer bar injection

| Stage | Tasks |
|-------|-------|
| Build | MarketState(specs={"ESH26": ESH26_ContractSpec}) |
| Build | Engine with StrategizerStrategyAdapter(ORB5mStrategy(...)) |
| Feed | engine.on_bar(bar) for each bar |
| Collect | TradeCandidates from second bar (breakout) |
| Assert | candidate.symbol="ESH26", direction=LONG, entry_price=5410.25 |

### Phase 2: Backtester run

| Stage | Tasks |
|-------|-------|
| Run | Backtester with golden config (120) |
| Collect | Orders from result |
| Assert | Order: instrument_id="ESH26", side="BUY", limit_price=5410.25 |

### Phase 3: Cross-tool assertion

| Stage | Tasks |
|-------|-------|
| Implement | test_orb_consistency_observer_backtester |
| Assert | candidate.entry_price == order.limit_price; symbol and direction match |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Fixture source | Reuse 120 golden bars, adapt to observer Bar | Single canonical sequence |
| Comparison depth | Entry intent (symbol, direction, entry_price) | Stop/targets internal; MVP focuses on entry |
| Test location | backtester/tests/integration/ | Owns fixture; observer as optional dev dep |
| Dependency | observer-backend as optional dev dep | Enables full cross-tool test |

---

## Alternative: Strategizer-Only Validation

If observer dependency is undesirable: run strategizer ORB directly, compare Signals to backtester Orders. Validates backtester adapter only; does not validate observer. Plan 130 prefers full cross-tool run.

---

## Acceptance Criteria

- [ ] Same bar sequence produces ORB signal in both tools
- [ ] Entry prices match (5410.25, within tick)
- [ ] Symbol and direction match
- [ ] Documented validation procedure

---

## Open Decisions

| Topic | Options |
|-------|---------|
| Dependency | Full observer import vs. strategizer-only fallback |
| CI | Skip E2E when observer unavailable vs. require both projects |

---

## Out of Scope

- Exit order comparison
- Performance parity
- UI validation
