---
name: 090 Backtester Fill Model Futures
overview: "Extend fill model to produce tick-aligned fill prices for futures. Use FuturesContractSpec.tick_size. Maintain determinism."
todos: []
isProject: false
---

# 090: Backtester Fill Model Futures

Conforms to [000_strategizer_mvp_plan.md](000_strategizer_mvp_plan.md) §5.3.

---

## Objective

Extend the backtester fill model so that futures fills use tick-aligned prices. When filling a futures order, the fill_price must be rounded to the contract's tick_size (e.g., ES: 0.25). Maintain determinism.

---

## Existing Foundation

- fill_model.py: fill_order() uses bar close or quote bid/ask
- For underlying: synthetic spread around bar close
- For options: bid/ask or synthetic spread
- Step 070: FuturesContractSpec with tick_size
- observer core/tick: normalize_price — backtester should not import observer; implement locally or in shared utils

---

## Futures Fill Logic

When instrument_type == "future":
1. Use underlying_bar.close as mid (futures bar)
2. Apply synthetic spread: mid +/- half_spread (same as equity)
3. **Tick-align** the result: round to nearest tick_size
4. Return Fill with tick-aligned fill_price

**Implementation note:** Apply tick alignment at the end of fill_order, after any fill_price path. When futures_spec is provided, tick-align before returning—regardless of whether the fill came from bar or quote. Future-proofs for quote-based futures if added later.

---

## Tick Normalization

Options:
1. Copy normalize_price logic to backtester (Decimal-based)
2. Add backtester/src/utils/tick.py
3. Use strategizer.tick (strategizer already has normalize_price)—would add strategizer dep at 090

**Recommendation:** Add backtester/src/utils/tick.py with normalize_price(price, tick_size) -> float. Same logic as observer/strategizer (Decimal, ROUND_HALF_EVEN). Keeps backtester self-contained until 100 adds strategizer.

---

## fill_order Signature

Current: fill_order(order, snapshot, symbol="", fill_config=None)

For futures: need tick_size. Sources:
- Pass FuturesContractSpec to fill_order
- Pass tick_size as param
- fill_config includes tick_size when instrument_type=future

Extend: `fill_order(..., futures_spec: FuturesContractSpec | None = None)`. When futures_spec provided, apply tick alignment to fill_price before returning.

---

## Implementation Phases

### Phase 0: Tick utility

| Stage | Tasks |
|-------|-------|
| Create | backtester/src/utils/tick.py: normalize_price(price, tick_size) -> float |
| Test | Unit tests: 5412.30, tick 0.25 -> 5412.25; 5412.375 -> 5412.50 (half-even); edge cases |
| Logic | Use Decimal internally; ROUND_HALF_EVEN; return float |

### Phase 1: Fill model extension

| Stage | Tasks |
|-------|-------|
| Extend | fill_order: add futures_spec param; when provided, tick-align fill_price before returning |
| Extend | submit_orders: add futures_contract_spec param; pass to fill_order |
| Test | Fill for futures order has tick-aligned price |

### Phase 2: Engine wiring

| Stage | Tasks |
|-------|-------|
| Wire | Engine passes config.futures_contract_spec to submit_orders when instrument_type=future |
| Note | Spec already in BacktestConfig (070); no DataProvider call needed for fill model |
| Test | Integration: futures backtest produces tick-aligned fills |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tick util location | backtester/src/utils/ | No observer dependency; self-contained until 100 |
| normalize_price | Same algo as observer/strategizer | Decimal-based; ROUND_HALF_EVEN; exact; avoid float drift |
| fill_order param | futures_spec optional | Backward compatible; None for options/equity |
| Spec source | config.futures_contract_spec | 070 already has it; no DataProvider call for fill model |

---

## Acceptance Criteria

- [ ] normalize_price(price, tick_size) implemented and tested (including half-even rounding)
- [ ] fill_order accepts futures_spec; tick-aligns when provided
- [ ] submit_orders accepts futures_contract_spec; passes to fill_order
- [ ] Engine passes config.futures_contract_spec when instrument_type=future
- [ ] Futures fills have tick-aligned prices
- [ ] Options/equity fills unchanged
- [ ] Deterministic

---

## Out of Scope

- Partial fills
- Slippage model
- Level2 simulation
