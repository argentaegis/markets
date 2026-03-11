---
name: 100 Backtester Strategizer Adapter
overview: "Implement adapter in backtester: MarketSnapshot + PortfolioState -> strategizer input; Signal -> Order. Qty from config (configurable, default 1)."
todos: []
isProject: false
---

# 100: Backtester Strategizer Adapter

Conforms to [000_strategizer_mvp_plan.md](000_strategizer_mvp_plan.md) §5.4 and §13.

---

## Objective

Implement the adapter that translates backtester's native types to/from strategizer types. Enables backtester to run strategies (e.g., ORB) from the strategizer package. Position sizing: configurable via strategy params, default 1 (per 000 §13).

---

## Existing Foundation

- Step 030: ORB5mStrategy in strategizer
- Step 070–090: Backtester supports futures
- backtester: MarketSnapshot (ts, underlying_bar, option_quotes), PortfolioState, Order
- strategizer: BarInput, Signal, PortfolioView, ContractSpecView

---

## Adapter Responsibilities

### Input: MarketSnapshot + PortfolioState → Strategizer

| Strategizer Input | Source |
|------------------|--------|
| ts | snapshot.ts |
| bars_by_symbol | underlying_bar → BarInput; key by config.symbol, timeframe |
| specs | FuturesContractSpec; implement ContractSpecView (tick_size, point_value, session) |
| portfolio | BacktesterPortfolioView wrapping PortfolioState |

For futures: snapshot.underlying_bar is the futures bar. Single symbol. bars_by_symbol[symbol][timeframe] = [BarInput(...)].

**Bar history:** Adapter converts what it receives. ORB needs lookback ~80 bars; snapshot has one bar. Extend signature with optional `bars: list[BarRow] | None = None`. When provided, use it; else fall back to snapshot.underlying_bar. Caller (110) fetches and passes history.

BarRow has: ts, open, high, low, close, volume. BarInput same. Map directly.

### Output: Signal → Order

| Order Field | Source |
|-------------|--------|
| id | uuid or deterministic (e.g. f"{strategy}-{symbol}-{direction}-{ts}") |
| ts | snapshot.ts |
| instrument_id | signal.symbol (futures: ESH26) |
| side | "BUY" if signal.direction=="LONG" else "SELL" |
| qty | from strategy config (qty param, default 1) |
| order_type | "market" if MARKET; "limit" if LIMIT; "stop" if STOP (see STOP Handling) |
| limit_price | signal.entry_price for LIMIT; signal.entry_price for STOP (stop level) |
| tif | "GTC" |

---

## Qty Handling

Per 000 §13: configurable, default 1.

Strategy config in backtest YAML:
```yaml
strategy:
  name: orb_5m
  params:
    min_range_ticks: 4
    max_range_ticks: 40
    qty: 1
```

Adapter reads qty from params when building Order from Signal.

---

## STOP Order Handling

ORB emits entry_type="STOP" (buy stop above breakout, sell stop below). Backtester Order has "market" | "limit"; no native stop.

**Semantic mismatch:** Buy STOP at 5415 fills when price >= 5415. Buy LIMIT at 5415 fills when price <= 5415. Mapping STOP → limit inverts fill logic.

**MVP options:**
1. Add order_type="stop" to Order; fill model (110) handles: BUY stop at X fills when bar high >= X
2. Approximate with order_type="market": fill at bar close of breakout bar (simpler, less accurate)
3. Emit order_type="stop", limit_price=entry_price; document that fill model must be extended in 110

**Recommendation:** Add order_type="stop" to Order. Adapter emits it. Step 110 extends fill model to handle stop orders (fill when bar crosses stop level).

---

## ContractSpecView

FuturesContractSpec has: symbol, tick_size, point_value, session (TradingSession).
ContractSpecView protocol: tick_size, point_value, timezone, start_time, end_time.

**Recommendation:** Add properties to FuturesContractSpec so it satisfies ContractSpecView structurally:
```python
@property
def timezone(self) -> str: return self.session.timezone
@property
def start_time(self) -> time: return self.session.start_time
@property
def end_time(self) -> time: return self.session.end_time
```
No separate adapter needed.

---

## Module Layout

```
backtester/src/
  strategies/
    strategizer_adapter.py   # snapshot_to_input, signal_to_order, BacktesterPortfolioView
```

---

## Implementation Phases

### Phase 0: Input adapter

| Stage | Tasks |
|-------|-------|
| Implement | snapshot_to_strategizer_input(snapshot, portfolio, symbol, timeframe, spec, bars=None) -> (ts, bars_by_symbol, specs, portfolio_view) |
| Note | When bars provided, use it; else bars_from_snapshot = [underlying_bar] if underlying_bar else [] |
| Implement | bar_row_to_bar_input(bar: BarRow) -> BarInput |
| Implement | BacktesterPortfolioView wrapping PortfolioState |
| Extend | FuturesContractSpec: add timezone, start_time, end_time properties (from session) |
| Test | Unit tests |

### Phase 1: Output adapter

| Stage | Tasks |
|-------|-------|
| Extend | Order: add order_type "stop" when not present |
| Implement | signal_to_order(signal, ts, qty) -> Order |
| Note | entry_type MARKET→market, LIMIT→limit, STOP→stop; limit_price=entry_price for limit/stop |
| Test | Signal -> Order has correct side, qty, order_type, limit_price |

### Phase 2: Integration

| Stage | Tasks |
|-------|-------|
| Add | strategizer as backtester dependency |
| Verify | Adapter functions work with real types |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Adapter location | backtester/strategies/strategizer_adapter.py | S3: adapters in consumer |
| qty source | Strategy params, default 1 | 000 §13 |
| order_type for STOP | Add "stop" to Order; emit it | LIMIT inverts fill semantics; stop needs dedicated handling in fill model (110) |
| ContractSpecView | Add properties to FuturesContractSpec | No separate adapter; protocol satisfied structurally |
| Bar history | Optional bars param; caller (110) provides | Adapter converts; ORB needs ~80 bars; engine/strategy fetches and passes |
| BarInput from BarRow | Direct mapping | Same fields; BarRow.ts, BarInput.ts |

---

## Acceptance Criteria

- [ ] snapshot_to_strategizer_input produces valid input (with optional bars param)
- [ ] signal_to_order produces valid Order with qty from config, correct order_type for MARKET/LIMIT/STOP
- [ ] BacktesterPortfolioView implements PortfolioView
- [ ] FuturesContractSpec satisfies ContractSpecView (timezone, start_time, end_time from session)
- [ ] Order supports order_type "stop" (fill model handling deferred to 110)
- [ ] backtester pyproject includes strategizer dependency

---

## Out of Scope

- Running ORB in engine (step 110)
- Bar history fetch (110: engine or strategy fetches; passes to adapter)
- Fill model stop order logic (110)
- Multi-symbol bars (single symbol for MVP)
