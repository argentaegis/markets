---
name: 150 Trailing Stops
overview: Add trailing stop support to backtester and implement trend_entry_trailing_stop strategy in strategizer. Depends on Plan 140 (Strategizer service).
todos: []
isProject: false
---

# 150: Trailing Stops and Trend Entry Strategy

## Prerequisite

Plan 140 complete. Strategizer runs as a service. Backtester and observer call it via HTTP. Four strategies (orb_5m, buy_and_hold, covered_call, buy_and_hold_underlying) working.

---

## Scope

1. **Backtester**: Trailing stop support — Order type, fill logic, position-level state
2. **Strategizer**: trend_entry_trailing_stop strategy — trend signal + trailing stop at entry
3. **Signal/API**: Add `trailing_stop_ticks` to Signal for strategies that use broker-managed trailing stops

---

## Strategy: trend_entry_trailing_stop

| Aspect | Design |
|--------|--------|
| **Entry (LONG)** | First bar where close crosses above MA. Emit only on transition: bars[-2].close < MA, bars[-1].close >= MA. |
| **Entry (SHORT)** | First bar where close crosses below MA. Emit only on transition: bars[-2].close > MA, bars[-1].close <= MA. |
| **Exit** | Trailing stop (broker-managed). Strategy emits `trailing_stop_ticks` in Signal. Backtester executes when price moves against by N ticks from water mark (high_water for longs, low_water for shorts). |
| **Spec** | Needs ContractSpecView (tick_size) for tick alignment |
| **Params** | ma_period, trailing_stop_ticks, qty, direction ("LONG" \| "SHORT", default LONG) |

---

## Backtester: Trailing Stop Implementation

### Problem

Trailing stops require position-level state: (entry_ts, high_water/low_water, trailing_stop_ticks). The fill model is stateless per order. A trailing stop is evaluated each step while the position exists.

### Approach

1. **Order**: Add `trailing_stop_ticks: int | None = None`. When set, order represents "entry + trailing stop attached."
2. **TrailingStopManager**: New component. Each step, receives (portfolio, snapshot, tick_size_map). For each position with trailing_stop_ticks: update water mark from bar; check trigger; return synthetic exit fills and orders.
3. **Engine**: After normal order processing, call TrailingStopManager. Apply any returned fills to portfolio via apply_fill (requires both Fill and Order).
4. **State**: TrailingStopManager tracks per-instrument state. Key = `instrument_id` (one trailing stop per instrument). Populate from filled orders that had trailing_stop_ticks (use order_id→Order map when processing fills). Clear state when position closes (trailing stop triggers).
5. **Empty bar**: When `snapshot.underlying_bar` (or futures bar) is None, skip trigger check for that step; do not update water mark.

### Phase 1: Order and Fill Model

1. Add `trailing_stop_ticks: int | None = None` to Order
2. When converting Signal to Order: if `signal.trailing_stop_ticks` set, include in Order
3. When applying fills: pass (fill, order) to TrailingStopManager.register_fill(); when order.trailing_stop_ticks is set, add/update state for instrument_id

### Phase 2: TrailingStopManager

1. Create `TrailingStopManager` in backtester
2. **State**: Key = `instrument_id`. Value = (entry_ts, water_mark, trailing_stop_ticks, side). Populate from fills whose Order had `trailing_stop_ticks`; clear when position closes. Initial water_mark on first evaluation: high_water = bar.high (long), low_water = bar.low (short).
3. **Long positions** (qty > 0): high_water = max(high_water, bar.high). Trigger when bar.low <= high_water - N×tick_size. Fill price = high_water - N×tick_size (trigger price).
4. **Short positions** (qty < 0): low_water = min(low_water, bar.low). Trigger when bar.high >= low_water + N×tick_size. Fill price = low_water + N×tick_size (trigger price).
5. **Synthetic exit**: Returns list of (Fill, Order) pairs. Order: id=`trailing-{instrument_id}-{ts.isoformat()}`, side=opposite of position, qty=abs(position.qty). Fill: order_id matches, fill_price=trigger price. `apply_fill` consumes both.
6. **Tick size**: From `futures_contract_spec.tick_size` when instrument_type=future; default 0.01 for equity/options. Pass tick_size_map: instrument_id → float to manager.
7. **Empty bar**: Skip step when no bar; do not update water mark or check trigger.
8. Engine integrates: call after submit_orders and apply_fill; apply trailing stop fills.

### Phase 3: strategizer Signal and trend_entry_trailing_stop

1. Add `trailing_stop_ticks: int | None = None` to Signal (strategizer API)
2. Implement trend_entry_trailing_stop in strategizer service
3. First-cross rule: emit buy only when bars[-2].close < MA and bars[-1].close >= MA
4. Include trailing_stop_ticks from strategy_params in emitted Signal

---

## Signal Extension (Plan 150)

```json
{
  "symbol": "ESH26",
  "instrument_id": null,
  "direction": "LONG",
  "entry_type": "MARKET",
  "entry_price": 0,
  "stop_price": 0,
  "targets": [],
  "qty": 1,
  "trailing_stop_ticks": 10
}
```

- `trailing_stop_ticks`: optional; when set, backtester attaches trailing stop to position
- `direction`: "LONG" or "SHORT"; determines water mark (high_water vs low_water) and trigger direction

---

## Implementation Phases

### Phase 1: Order and Signal Schema

1. Add `trailing_stop_ticks` to backtester Order
2. Add `trailing_stop_ticks` to strategizer Signal (API response schema)
3. Backtester HTTP client: map `trailing_stop_ticks` from response to Order

### Phase 2: TrailingStopManager

1. Implement TrailingStopManager with high-water mark tracking
2. Integrate into engine loop (after order processing)
3. Unit tests for trigger logic

### Phase 3: trend_entry_trailing_stop Strategy

1. Implement in strategizer service
2. First-cross entry rule; ma_period, trailing_stop_ticks from strategy_params
3. Config and example YAML

### Phase 4: Integration Tests

1. Backtest trend_entry_trailing_stop with fixture data
2. Assert entry on first cross, exit when trailing stop triggers
3. Unit tests: long trigger (bar.low <= high_water - N×tick), short trigger (bar.high >= low_water + N×tick)
4. Unit tests: empty bar skips; water mark updates correctly

---

## Engine Loop Order

1. Strategy.on_step → orders
2. submit_orders → fills
3. For each fill: apply_fill; TrailingStopManager.register_fill(fill, order) when order.trailing_stop_ticks
4. TrailingStopManager.evaluate(portfolio, snapshot, tick_size_map) → [(Fill, Order), ...]; uses current bar for water mark and trigger
5. For each trailing fill: apply_fill; clear state for that instrument_id
6. mark_to_market
7. Expirations, invariants, equity curve, etc.

---

## Risks

| Risk | Mitigation |
|------|------------|
| High-water/low-water state complexity | Clear TrailingStopManager interface; unit test longs and shorts |
| First-cross may miss in choppy data | Document; accept for MVP testing |
| Synthetic Order/Fill coupling | Return (Fill, Order) pairs; apply_fill accepts both |
