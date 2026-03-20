---
name: 070 Backtester Futures Domain
overview: "Add ContractSpec for futures, extend Position and fill logic for instrument_type 'future', support tick_size and point_value. Enables backtester to run futures strategies."
todos: []
isProject: false
---

# 070: Backtester Futures Domain

Conforms to [000_strategizer_mvp_plan.md](000_strategizer_mvp_plan.md) §5.1.

---

## Objective

Extend the backtester domain to support futures. Add ContractSpec for futures (tick_size, point_value, session). Extend Position and fill/accounting logic for `instrument_type: "future"`. MarketSnapshot for futures runs uses `underlying_bar` as the futures bar; `option_quotes` is None.

---

## Existing Foundation

- backtester: Order, Fill, Position, PortfolioState, MarketSnapshot
- backtester domain/contract.py: ContractSpec for options (strike, expiry, right, multiplier)
- backtester engine: _instrument_params() returns (multiplier, instrument_type) for equity vs option
- observer: ContractSpec (tick_size, point_value, session), TradingSession

---

## Target Domain

### FuturesContractSpec (or extend ContractSpec)

Options ContractSpec has: contract_id, underlying_symbol, strike, expiry, right, multiplier.

Futures need: symbol, tick_size, point_value, session (timezone, start_time, end_time).

Options:
1. New FuturesContractSpec in domain/futures.py
2. Extend ContractSpec with optional fields; discriminator by instrument_type
3. Union type: ContractSpec = OptionContractSpec | FuturesContractSpec

**Recommendation:** New `FuturesContractSpec` in domain/futures.py. Keeps options logic unchanged. Engine and DataProvider branch on instrument_type.

```python
@dataclass(frozen=True)
class FuturesContractSpec:
    symbol: str           # e.g. "ESH26", "NQH26"
    tick_size: float      # e.g. 0.25 for ES
    point_value: float    # e.g. 50 for ES, 20 for NQ
    session: TradingSession  # RTH hours, timezone
```

TradingSession: name, start_time, end_time, timezone (reuse from observer or add minimal version).

---

## Position and Fill Logic

### instrument_type

Position already has `instrument_type: str` ("option" | "underlying"). Add "future".

### multiplier

For futures: multiplier = point_value from ContractSpec (ES=50, NQ=20).
Engine's _instrument_params() must accept ContractSpec or config for futures to get multiplier.

### Tick alignment

Fill prices for futures must be tick-aligned. Add step 090 (fill model) for that; here just ensure domain supports it.

---

## Engine Changes

### _instrument_params

Today: `instrument_id == symbol` → equity (multiplier 1.0), else option (100.0).

For futures: when `instrument_type: future`, multiplier from FuturesContractSpec.point_value.
Engine needs access to contract specs for the run — from BacktestConfig or DataProvider.

### BacktestConfig

Add `instrument_type: str` ("equity" | "option" | "future").
Add optional `futures_contract_spec: FuturesContractSpec` or resolve from DataProvider.

### Broker interface

`validate_order` uses `multiplier` for buying-power checks. For futures, `instrument_id == symbol`, so current heuristic (1.0) is wrong. Extend `submit_orders` to accept `multiplier: float | None = None`. When `instrument_type == "future"`, engine passes `multiplier=futures_spec.point_value`. When `None`, retain current behavior (equity/option heuristic).

### Expiration

`_detect_expirations` uses option ContractSpec expiry; futures have no intraday expiration. When `instrument_type == "future"`, skip expiration logic (return `{}` or do not call).

### Engine scope (070 vs 080)

070: Config, `_instrument_params`, DataProvider stub. Full snapshot wiring (get_futures_bars, build snapshot) deferred to 080.

---

## Implementation Phases

### Phase 0: FuturesContractSpec, TradingSession

| Stage | Tasks |
|-------|-------|
| Create | domain/futures.py: FuturesContractSpec, TradingSession (or import from shared if extracted) |
| Test | Unit tests for FuturesContractSpec |

### Phase 1: Position support

| Stage | Tasks |
|-------|-------|
| Extend | Position.instrument_type accepts "future" |
| Note | apply_fill, mark_to_market already accept multiplier, instrument_type; no code change |

### Phase 2: Config and engine

| Stage | Tasks |
|-------|-------|
| Extend | BacktestConfig: instrument_type, futures_contract_spec (optional) |
| Extend | Engine _instrument_params: when config.instrument_type=="future", return (spec.point_value, "future") |
| Extend | submit_orders: add multiplier param; pass to validate_order when provided |
| Extend | Engine: when instrument_type=="future", skip _detect_expirations (or return {}) |
| Extend | DataProvider: get_futures_contract_spec(symbol) — stub raises NotImplementedError until 080 |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| FuturesContractSpec | Separate from options ContractSpec | Different fields; avoids optional overload |
| TradingSession | Copy minimal def to backtester | No observer dependency (S1) |
| multiplier for futures | point_value | ES point = $50; NQ = $20; standard convention |
| Broker multiplier | submit_orders accepts multiplier param | validate_order needs correct mult for futures buying power |
| Expiration for futures | Skip _detect_expirations | Futures have no intraday expiration in this model |

---

## Acceptance Criteria

- [ ] FuturesContractSpec defined (domain/futures.py)
- [ ] Position accepts instrument_type "future"
- [ ] apply_fill, mark_to_market work with instrument_type "future" (no code change; multiplier passed correctly)
- [ ] BacktestConfig supports instrument_type, futures_contract_spec
- [ ] Engine _instrument_params returns (point_value, "future") when instrument_type=future
- [ ] submit_orders accepts multiplier for futures runs
- [ ] Engine skips _detect_expirations when instrument_type=future
- [ ] DataProvider.get_futures_contract_spec stub (raises NotImplementedError)

---

## Files to Touch

| File | Change |
|------|--------|
| src/domain/futures.py (new) | FuturesContractSpec, TradingSession |
| src/domain/position.py | Docstring: instrument_type "option" \| "underlying" \| "future" |
| src/domain/config.py | BacktestConfig: instrument_type, futures_contract_spec |
| src/engine/engine.py | _instrument_params, _process_orders, _detect_expirations |
| src/broker/broker.py | submit_orders, validate_order: multiplier param |
| src/loader/provider.py | DataProvider: get_futures_contract_spec stub |

---

## Out of Scope

- DataProvider futures data (step 080)
- Fill model tick alignment (step 090)
- Strategizer adapter (step 100)
