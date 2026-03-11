---
name: 020 Shared Types
overview: "Test and refine BarInput, PositionView, Signal, PortfolioView, ContractSpecView, Requirements. Types may already exist from step 010; this step adds tests and fixes any gaps (e.g., ContractSpecView typing)."
todos: []
isProject: false
---

# 020: Shared Types

Conforms to [000_strategizer_mvp_plan.md](000_strategizer_mvp_plan.md) §3.

---

## Project Practice: Test-First

| Stage | Description |
|-------|--------------|
| **Red** | Write failing tests. Run tests; they fail. |
| **Green** | Implement or fix code. Run tests; they pass. |
| **Refactor** | Clean up while keeping tests green. |

---

## Objective

Test and refine the shared domain types that form the contract between strategizer and its consumers. Types may already exist from step 010; this step adds unit tests and fixes any gaps (e.g., incomplete type hints in ContractSpecView). Ensures types are correct and stable for steps 030, 050, 100.

---

## Existing Foundation

- Step 010: strategizer package exists, installs, pytest runs
- types.py, protocol.py, base.py likely exist (may be full implementations, not stubs)
- This step adds tests and refines as needed

---

## Target Types

### types.py

| Type | Fields | Notes |
|------|--------|-------|
| `BarInput` | ts, open, high, low, close, volume | Minimal OHLCV; frozen dataclass |
| `PositionView` | instrument_id, qty, avg_price | Read-only position snapshot; frozen |
| `Signal` | symbol, direction, entry_type, entry_price, stop_price, targets, score, explain, valid_until | Trading intent; score/explain/valid_until optional |

### protocol.py

| Type | Purpose |
|------|---------|
| `PortfolioView` | Protocol: get_positions() -> dict[str, PositionView], get_cash() -> float, get_equity() -> float |
| `ContractSpecView` | Protocol: tick_size, point_value, timezone, start_time, end_time. **start_time/end_time must be typed `-> time`** (add `from datetime import time`). Observer/backtester implement via adapters (e.g. observer wraps ContractSpec.session). |
| `Requirements` | Dataclass: symbols, timeframes, lookback, needs_quotes |

### base.py

| Type | Purpose |
|------|---------|
| `Strategy` | ABC: name, requirements(), evaluate(ts, bars_by_symbol, specs, portfolio) -> list[Signal] |

---

## Module Layout

```
strategizer/src/strategizer/
  types.py       # BarInput, PositionView, Signal
  protocol.py    # PortfolioView, ContractSpecView, Requirements
  base.py        # Strategy ABC

strategizer/tests/
  test_types.py
  test_protocol.py
  test_base.py
```

---

## Implementation Phases

### Phase 1: BarInput, PositionView, Signal

| Stage | Tasks |
|-------|-------|
| **Red** | test_types.py: BarInput creation, immutability (FrozenInstanceError on field assignment), all fields; PositionView creation; Signal creation with required and optional fields |
| **Green** | Implement or fix types.py if tests fail |
| **Refactor** | Ensure frozen dataclasses |

BarInput has no validation (no NaN/negative checks); consumers validate before adapting. Keeps strategizer minimal.

### Phase 2: PortfolioView, ContractSpecView, Requirements

| Stage | Tasks |
|-------|-------|
| **Red** | test_protocol.py: Mock implementing PortfolioView; MockContractSpecView with start_time/end_time as `datetime.time` (e.g. `time(9, 30)`, `time(16, 0)`); Requirements dataclass |
| **Green** | Implement or fix protocol.py. **Fix ContractSpecView: add `-> time` for start_time and end_time; add `from datetime import time`** |
| **Refactor** | Verify protocols work with structural typing |

### Phase 3: Strategy ABC

| Stage | Tasks |
|-------|-------|
| **Red** | test_base.py: Strategy cannot be instantiated (TypeError); minimal concrete subclass (returns [] from evaluate, has name and requirements) works |
| **Green** | Implement or fix base.py |
| **Refactor** | Clean type hints (BarInput in evaluate signature) |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| BarInput | No symbol, timeframe | Adapters add context; strategizer receives pre-keyed bars_by_symbol |
| Signal.valid_until | Optional | Backtester may not use; observer requires it |
| Protocols | Structural (typing.Protocol) | Consumers implement without inheriting; loose coupling |
| Requirements | In strategizer | Strategies declare needs; engine uses for data validation |
| ContractSpecView.start_time/end_time | Typed as `datetime.time` | Enables type checking; observer adapter wraps ContractSpec.session |
| BarInput validation | None | Consumers validate; strategizer stays minimal |

---

## Acceptance Criteria

- [ ] BarInput, PositionView, Signal defined and tested
- [ ] PortfolioView, ContractSpecView protocols defined; MockContractSpecView with typed start_time/end_time passes
- [ ] Requirements dataclass defined
- [ ] Strategy ABC defined with evaluate() signature matching 000 §3.4
- [ ] Minimal concrete Strategy subclass passes
- [ ] `pytest` passes (run from strategizer/)

---

## Out of Scope

- ORB strategy implementation (step 030)
- Adapter implementations (steps 050, 100)
