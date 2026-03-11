# 255: trend_follow_risk_sized — Portfolio-Aware Trend Strategy

## Objective

Add a new strategy `trend_follow_risk_sized` that makes genuine use of the `PortfolioView` interface:
- **Avoids re-entry** when already positioned (uses `get_positions`)
- **Sizes qty from risk budget** as a fraction of current equity (uses `get_equity`)
- **Guards against insufficient cash** before emitting a signal (uses `get_cash`)

This is the first strategy in the codebase that reads portfolio state to drive its logic.

---

## Entry Logic

Same MA-cross signal as `trend_entry_trailing_stop`:
- LONG: bar `low[-2] < MA` and bar `low[-1] >= MA`
- SHORT: bar `high[-2] > MA` and bar `high[-1] <= MA`

Same broker-managed trailing stop exit via `Signal.trailing_stop_ticks`.

---

## Portfolio-Aware Changes

### 1. No re-entry when already positioned

```python
positions = portfolio.get_positions()
if symbol in positions:
    continue   # already in trade, skip signal
```

`trend_entry_trailing_stop` can double up if the MA-cross fires again before the trailing stop exits. `trend_follow_risk_sized` skips entry completely when a position already exists for the symbol.

**Note on key alignment**: `get_positions()` returns instrument_ids as keys. For futures the broker
sets `instrument_id = signal.instrument_id or signal.symbol or config.symbol`, and since
`Signal.instrument_id` is `None` here the position key equals `config.symbol`. So `symbol in
positions` is a reliable flat/positioned check for this strategy type.

### 2. Risk-based quantity sizing

```python
equity = portfolio.get_equity()
risk_dollars = risk_pct * equity                         # e.g. 0.01 * 500_000 = $5_000
stop_distance = trailing_stop_ticks * tick_size          # ticks → price points
stop_dollars = stop_distance * point_value               # price points → $/contract
if stop_dollars <= 0:
    qty = 1                                              # guard: zero ticks or degenerate spec
else:
    qty = int(risk_dollars / stop_dollars)               # e.g. $5000 / $125 = 40
qty = max(1, min(qty, max_qty))                          # floor 1, cap at max_qty
```

Parameters:
- `risk_pct` (float, default `0.01`): fraction of equity to risk per trade
- `max_qty` (int, default `10`): hard cap to prevent runaway sizing

### 3. Cash sufficiency guard

```python
cost_per_contract = current_price * point_value
estimated_cost = qty * cost_per_contract
if portfolio.get_cash() < estimated_cost:
    qty = int(portfolio.get_cash() / cost_per_contract)
if qty <= 0:
    continue   # can't afford even 1 contract; skip signal
```

Uses the last bar's close as `current_price`.

**Cash model caveat**: the backtester accounts for futures using full notional value (mark × qty ×
point_value), not exchange margin. This is consistent with how `broker.validate_order` checks
buying power. Concretely, 1 ES contract at 5400 "costs" $270,000 against cash. Set `initial_cash`
in configs at notional scale (e.g. $500,000 for ~1 ES contract), not at broker margin scale.

---

## Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `symbols` | list[str] | `["ES"]` | Symbols to trade |
| `ma_period` | int | `20` | SMA period |
| `trailing_stop_ticks` | int | `10` | Ticks for broker trailing stop |
| `direction` | str | `"LONG"` | `"LONG"` or `"SHORT"` |
| `timeframe` | str | `"1m"` | Bar timeframe |
| `risk_pct` | float | `0.01` | Fraction of equity to risk per trade |
| `max_qty` | int | `10` | Hard cap on position size |

---

## Deliverables

### 1. `strategizer/src/strategizer/strategies/trend_follow_risk_sized.py`

New strategy class. Follows the same pattern as `trend_entry_trailing_stop` but replaces the fixed
`qty` param with risk-based sizing and adds portfolio checks.

### 2. `strategizer/src/strategizer/strategies/__init__.py`

Add `TrendFollowRiskSizedStrategy` to `STRATEGY_REGISTRY`:

```python
from strategizer.strategies.trend_follow_risk_sized import TrendFollowRiskSizedStrategy

STRATEGY_REGISTRY = {
    ...existing...,
    "trend_follow_risk_sized": TrendFollowRiskSizedStrategy,
}
```

### 3. `backtester/src/strategies/strategizer_adapter.py`

Add a new `elif` branch in `StrategizerStrategy.__init__` so the correct symbol and parameters
are wired in at construction time (without this, `cls()` falls through to defaults and uses
`symbols=["ES"]` regardless of `config.symbol`):

```python
elif strategy_name == "trend_follow_risk_sized":
    init_kwargs = {
        "symbols": [config.symbol],
        "ma_period": self._strategy_params.get("ma_period", 20),
        "trailing_stop_ticks": self._strategy_params.get("trailing_stop_ticks", 10),
        "direction": self._strategy_params.get("direction", "LONG"),
        "timeframe": config.timeframe_base,
        "risk_pct": self._strategy_params.get("risk_pct", 0.01),
        "max_qty": self._strategy_params.get("max_qty", 10),
    }
```

### 4. `backtester/src/runner.py`

Add `"trend_follow_risk_sized"` to `STRATEGY_NAMES`.

### 5. `strategizer/tests/test_trend_follow_risk_sized.py`

Unit tests covering:

| Test | Assertion |
|------|-----------|
| No signal when already positioned | `get_positions` returns `{symbol: pos}` → empty signal list |
| Signal emitted when flat | returns 1 signal with correct side |
| Qty scales with equity | equity × 2 → qty × 2 (within max_qty cap) |
| max_qty caps oversized accounts | very large equity → qty == max_qty |
| Cash-insufficient reduces qty | `get_cash` too low for full qty → reduced qty |
| Cash-zero suppresses signal | `get_cash == 0` → empty signal list (qty=0, not max(1,0)) |
| Zero trailing_stop_ticks: no crash | `trailing_stop_ticks=0` → qty falls back to 1, no ZeroDivisionError |
| LONG direction: MA cross fires correctly | same as trend_entry_trailing_stop tests |
| SHORT direction: MA cross fires correctly | same |
| Insufficient bars: no signal | `len(bars) < ma_period + 1` → empty |
| `trailing_stop_ticks` passed through | signal has correct `trailing_stop_ticks` |

### 6. `backtester/configs/trend_follow_risk_sized_example.yaml`

Example config using ES futures, `risk_pct: 0.01`, `max_qty: 5`.

---

## Sizing Example

```
equity:                 $500,000
risk_pct:                    1%
risk_dollars:             $5,000
trailing_stop_ticks:          10
tick_size:               $0.25/tick
stop_distance:     10 × $0.25 = $2.50 price movement
point_value:              $50/pt
stop_value/contract: $2.50 × $50 = $125
raw qty:           $5,000 / $125 = 40
max_qty cap:                   5
→ qty emitted:                 5
```

The cap exists because a 1m futures strategy on a 500k account could produce dangerously large
positions without it. `max_qty` is an explicit user-controlled safety valve.

---

## What is NOT changing

- No changes to engine, broker, or portfolio package
- `_BacktesterPortfolioView` in the adapter already exposes all three required methods
- `trend_entry_trailing_stop` unchanged — this is an additive strategy

---

## Verification

```bash
# Unit tests for new strategy
pytest strategizer/tests/test_trend_follow_risk_sized.py -v

# Full suite — no regressions
pytest backtester/tests/ -v
pytest strategizer/ -v

# Backtest run using example config
python -m src.runner configs/trend_follow_risk_sized_example.yaml
```

Expected: strategy fires same MA-cross entries as `trend_entry_trailing_stop`, but:
- Never holds more than `max_qty` contracts
- Never re-enters while a position is open
- `summary.json` shows fewer trades on a month-long run (no duplicates)

---

## Files

| File | Action |
|------|--------|
| `strategizer/src/strategizer/strategies/trend_follow_risk_sized.py` | New |
| `strategizer/src/strategizer/strategies/__init__.py` | Add to registry |
| `backtester/src/strategies/strategizer_adapter.py` | Add `elif` branch for symbol wiring |
| `strategizer/tests/test_trend_follow_risk_sized.py` | New |
| `backtester/src/runner.py` | Add to `STRATEGY_NAMES` |
| `backtester/configs/trend_follow_risk_sized_example.yaml` | New |
