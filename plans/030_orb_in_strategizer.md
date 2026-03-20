---
name: 030 ORB in Strategizer
overview: "Implement ORB 5m strategy in strategizer. Extract logic from observer ORB; consume BarInput, ContractSpecView, PortfolioView; emit Signal. Test-first with canned bar data."
todos: []
isProject: false
---

# 030: ORB 5m Strategy in Strategizer

Conforms to [000_strategizer_mvp_plan.md](000_strategizer_mvp_plan.md) §3.4 and §6.

---

## Project Practice: Test-First

| Stage | Description |
|-------|--------------|
| **Red** | Write failing tests with canned bar sequences. |
| **Green** | Implement ORB logic. |
| **Refactor** | Extract helpers; clean up. |

---

## Objective

Implement the Opening Range Breakout (5-minute) strategy in strategizer. This is the reference strategy that will run in both observer and backtester. Logic is extracted from [observer strategies/orb_5m.py](../observer/backend/src/strategies/orb_5m.py) and adapted to the strategizer interface.

---

## Existing Foundation

- Step 020: BarInput, Signal, PortfolioView, ContractSpecView, Requirements, Strategy ABC
- Observer ORB: [110_orb_5m_strategy.md](110_orb_5m_strategy.md) documents full logic
- Observer core/tick: normalize_price, ticks_between — strategizer needs equivalent (copy or minimal reimpl)

---

## Strategy Logic (from observer 110)

### Opening Range

- First 5m bar after RTH session open → OR high/low
- Session from ContractSpecView (timezone, start_time, end_time)
- Filters: min_range_ticks, max_range_ticks (configurable)

### Breakout Detection

- Bar close > OR high → LONG
- Bar close < OR low → SHORT
- Once per direction per session (no repeat signals)

### Entry / Stop / Targets

| Field | LONG | SHORT |
|-------|------|-------|
| Entry | OR high + 1 tick | OR low - 1 tick |
| Stop | OR low - 1 tick | OR high + 1 tick |
| T1 | Entry + 1R | Entry - 1R |
| T2 | Entry + 2R | Entry - 2R |

R = |entry - stop|. All prices tick-normalized.

---

## Interface Contract

### Constructor

```python
class ORB5mStrategy(Strategy):
    def __init__(
        self,
        symbols: list[str] | None = None,
        min_range_ticks: int = 4,
        max_range_ticks: int = 40,
    ) -> None: ...
```

### evaluate()

```python
def evaluate(
    self,
    ts: datetime,
    bars_by_symbol: dict[str, dict[str, list[BarInput]]],
    specs: dict[str, ContractSpecView],
    portfolio: PortfolioView,
) -> list[Signal]: ...
```

- bars_by_symbol[symbol]["5m"] = list of BarInput (ascending ts)
- specs[symbol] provides tick_size, point_value, session (timezone, start_time, end_time)
- portfolio: mock for MVP; used for future exit logic

---

## Tick Utilities

Strategizer needs `normalize_price` and `ticks_between`. Options:

1. Copy minimal implementation from observer core/tick (no observer import)
2. Add simple implementation in strategizer (Decimal-based, same logic)

Choose (2) to keep strategizer self-contained. Add `strategizer/utils.py` or `strategizer/tick.py`.

---

## Module Layout

```
strategizer/src/strategizer/
  utils.py         # normalize_price, ticks_between (or tick.py)
  strategies/
    orb_5m.py      # ORB5mStrategy

strategizer/tests/
  test_orb_5m.py   # Canned bar sequences, assert Signals
```

---

## Implementation Phases

### Phase 0: Tick utilities

| Stage | Tasks |
|-------|-------|
| **Red** | test_tick.py: normalize_price rounds correctly; ticks_between counts ticks |
| **Green** | Implement utils.tick or utils.py |

### Phase 1: OR identification

| Stage | Tasks |
|-------|-------|
| **Red** | test_orb_5m.py: Given bars with first RTH bar, identify OR high/low; new session resets state; range filters reject extreme OR |
| **Green** | Implement OR identification |

### Phase 2: Breakout detection

| Stage | Tasks |
|-------|-------|
| **Red** | Bar close > OR high → LONG Signal; bar close < OR low → SHORT; once per direction |
| **Green** | Implement breakout logic |

### Phase 3: Signal construction

| Stage | Tasks |
|-------|-------|
| **Red** | Entry, stop, targets correct; score heuristic; explain bullets; valid_until |
| **Green** | Build Signal objects |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tick utils | In strategizer (no observer import) | S1: strategizer has no dependency on observer |
| Session state | Mutable instance vars | ORB needs _or_high, _or_low, _session_date, _fired; same as observer |
| Portfolio use | Ignored for MVP | Mock returns empty; future steps add exit logic |
| ContractSpecView | Protocol with timezone, start_time, end_time | Observer ContractSpec and backtester futures spec both provide session |

---

## Acceptance Criteria

- [ ] ORB5mStrategy implements Strategy
- [ ] Correctly identifies OR from first 5m RTH bar
- [ ] Emits LONG/SHORT Signal on breakout
- [ ] Entry, stop, targets tick-normalized
- [ ] Range filters (min/max ticks) applied
- [ ] Once per direction per session
- [ ] Unit tests pass with canned bar data

---

## Out of Scope

- Observer/backtester adapters (steps 050, 100)
- Real portfolio integration (mock sufficient)
