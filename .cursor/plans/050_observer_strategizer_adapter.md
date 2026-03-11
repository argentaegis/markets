---
name: 050 Observer Strategizer Adapter
overview: "Implement adapter layer in observer: Context -> strategizer input; Signal -> TradeCandidate. Enables observer to run strategies from strategizer package."
todos: []
isProject: false
---

# 050: Observer Strategizer Adapter

Conforms to [000_strategizer_mvp_plan.md](000_strategizer_mvp_plan.md) §4.2 and S3.

---

## Objective

Implement the adapter that translates observer's native types to/from strategizer types. This allows observer to run strategies (e.g., ORB) from the strategizer package instead of (or in addition to) local strategies.

---

## Existing Foundation

- Step 030: ORB5mStrategy in strategizer
- Step 040: Observer has PortfolioState, Context includes portfolio
- observer: Context (timestamp, quotes, bars, specs, portfolio), TradeCandidate
- strategizer: BarInput, Signal, PortfolioView, ContractSpecView

---

## Adapter Responsibilities

### Input: Context → Strategizer

Portfolio comes from `ctx.portfolio` (040 adds portfolio to Context). Signature: `context_to_strategizer_input(ctx)`.

| Strategizer Input | Source |
|------------------|--------|
| ts | ctx.timestamp |
| bars_by_symbol | ctx.bars — map Bar → BarInput per symbol/timeframe |
| specs | ctx.specs — adapt each ContractSpec via ContractSpecViewAdapter |
| portfolio | ObserverPortfolioView(ctx.portfolio) |

### Output: Signal → TradeCandidate

| TradeCandidate Field | Source |
|---------------------|--------|
| id | uuid.uuid4() |
| symbol | signal.symbol |
| strategy | strategy.name |
| direction | signal.direction → Direction enum |
| entry_type | signal.entry_type → EntryType enum |
| entry_price | signal.entry_price |
| stop_price | signal.stop_price |
| targets | signal.targets |
| score | signal.score |
| explain | signal.explain |
| valid_until | signal.valid_until or created_at + timedelta(hours=1) |
| tags | {"strategy": name, "source": "strategizer"} |
| created_at | ctx.timestamp |

---

## BarInput Adapter

Observer Bar has: symbol, timeframe, open, high, low, close, volume, timestamp, source, quality

BarInput needs: ts, open, high, low, close, volume

```python
def bar_to_bar_input(bar: Bar) -> BarInput:
    return BarInput(ts=bar.timestamp, open=bar.open, high=bar.high,
                    low=bar.low, close=bar.close, volume=bar.volume)
```

---

## PortfolioView Adapter

Observer PortfolioState has: cash, positions (dict[str, Position])

Position: instrument_id, qty, avg_price (observer may add multiplier, instrument_type)

```python
class ObserverPortfolioView:
    """Adapts observer PortfolioState to strategizer PortfolioView."""
    def __init__(self, state: PortfolioState) -> None: ...
    def get_positions(self) -> dict[str, PositionView]:  # map Position → PositionView
    def get_cash(self) -> float: ...
    def get_equity(self) -> float: ...
```

For mock portfolio: equity = cash (no positions). Later: equity = cash + sum(mark_value).

---

## ContractSpecView Adapter

Observer ContractSpec has: symbol, instrument_type, tick_size, point_value, session (TradingSession)

TradingSession has: name, start_time, end_time, timezone

ContractSpecView protocol needs: tick_size, point_value, timezone, start_time, end_time (as top-level attributes)

ContractSpec nests timezone/start_time/end_time under `session`; structural typing does not match. A thin adapter is required:

```python
class ContractSpecViewAdapter:
    """Adapts observer ContractSpec to strategizer ContractSpecView."""
    def __init__(self, spec: ContractSpec) -> None:
        self._spec = spec
    @property
    def tick_size(self) -> float: return self._spec.tick_size
    @property
    def point_value(self) -> float: return self._spec.point_value
    @property
    def timezone(self) -> str: return self._spec.session.timezone
    @property
    def start_time(self) -> time: return self._spec.session.start_time
    @property
    def end_time(self) -> time: return self._spec.session.end_time
```

---

## Module Layout

```
observer/backend/src/
  strategies/
    strategizer_adapter.py   # context_to_strategizer_input, signal_to_trade_candidate,
                             # ObserverPortfolioView, ContractSpecViewAdapter
```

---

## Implementation Phases

### Phase 0: Input adapter

| Stage | Tasks |
|-------|-------|
| Prereq | Add `strategizer @ file:../../strategizer` to observer/backend/pyproject.toml |
| Implement | ContractSpecViewAdapter (thin wrapper for session.timezone, session.start_time, session.end_time) |
| Implement | context_to_strategizer_input(ctx) -> (ts, bars_by_symbol, specs, portfolio_view) |
| Note | Portfolio from ctx.portfolio; specs via ContractSpecViewAdapter |
| Test | Given Context with bars/specs, adapter produces correct BarInput dict and specs |

### Phase 1: Output adapter

| Stage | Tasks |
|-------|-------|
| Implement | signal_to_trade_candidate(signal, strategy_name, created_at) -> TradeCandidate |
| Note | valid_until: use signal.valid_until if set, else created_at + timedelta(hours=1) |
| Note | direction/entry_type: Direction(signal.direction), EntryType(signal.entry_type) |
| Test | Signal -> TradeCandidate has all required fields |

### Phase 2: PortfolioView

| Stage | Tasks |
|-------|-------|
| Implement | ObserverPortfolioView wrapping PortfolioState |
| Test | Mock portfolio -> get_positions empty, get_cash 0, get_equity 0 |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Adapter location | observer/strategies/strategizer_adapter.py | S3: adapters in consumer; name clarifies origin |
| strategy dep | observer pyproject: `strategizer @ file:../../strategizer` | Monorepo; path from observer/backend |
| ContractSpec | ContractSpecViewAdapter required | timezone/start_time/end_time nested under session |

---

## Acceptance Criteria

- [ ] context_to_strategizer_input(ctx) produces valid strategizer input (portfolio from ctx.portfolio)
- [ ] signal_to_trade_candidate() produces valid TradeCandidate
- [ ] ObserverPortfolioView implements PortfolioView
- [ ] Unit tests for adapters
- [ ] observer pyproject includes strategizer dependency

---

## Out of Scope

- Running ORB from strategizer in engine (step 060)
- Real portfolio (mock sufficient)

---

## Downstream Note

Step 060 wires this adapter. It should call `context_to_strategizer_input(ctx)` (no separate portfolio param); portfolio is in ctx.
